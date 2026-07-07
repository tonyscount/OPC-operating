"""
OA 审批 API

POST   /oa/templates           — 创建审批模板
GET    /oa/templates           — 模板列表
POST   /oa/apply               — 提交审批申请
GET    /oa/instances           — 我的申请列表
GET    /oa/instances/{id}      — 申请详情
GET    /oa/pending             — 待我审批
POST   /oa/approve/{step_id}   — 审批通过
POST   /oa/reject/{step_id}    — 审批拒绝
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.database import get_db
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.rate_limit import RATE_OA_APPLY, RATE_OA_APPROVE, limiter
from app.core.security import PermissionChecker, TokenPayload, get_current_user

router = APIRouter()
require_oa = PermissionChecker("oa:manage")


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_template(
    name: str,
    category: str,
    steps: list[dict],
    description: str | None = None,
    form_schema: dict | None = None,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """创建审批模板"""
    from app.modules.social.oa_models import ApprovalTemplate
    tpl = ApprovalTemplate(
        tenant_id=uuid.UUID(current_user.tenant_id),
        name=name, category=category, description=description,
        steps=steps, form_schema=form_schema or {},
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return {"id": str(tpl.id), "name": tpl.name, "category": tpl.category}


@router.get("/templates")
async def list_templates(
    category: str | None = None,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """审批模板列表"""
    from sqlalchemy import select
    from app.modules.social.oa_models import ApprovalTemplate

    conditions = [ApprovalTemplate.tenant_id == uuid.UUID(current_user.tenant_id)]
    if category:
        conditions.append(ApprovalTemplate.category == category)

    result = await db.execute(select(ApprovalTemplate).where(*conditions))
    tpls = result.scalars().all()
    return [{"id": str(t.id), "name": t.name, "category": t.category, "steps": t.steps} for t in tpls]


@router.post("/apply", status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_OA_APPLY)
async def submit_approval(
    request: Request,
    template_id: uuid.UUID,
    title: str,
    form_data: dict | None = None,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """提交审批申请"""
    from sqlalchemy import select
    from app.modules.social.oa_models import ApprovalTemplate, ApprovalInstance, ApprovalStep

    tpl = await db.get(ApprovalTemplate, template_id)
    if not tpl:
        raise NotFoundException("审批模板不存在")

    instance = ApprovalInstance(
        tenant_id=uuid.UUID(current_user.tenant_id),
        template_id=template_id,
        applicant_id=uuid.UUID(current_user.sub),
        title=title,
        form_data=form_data or {},
        total_steps=len(tpl.steps),
    )
    db.add(instance)
    await db.flush()

    # 创建审批步骤
    for step_def in tpl.steps:
        step = ApprovalStep(
            instance_id=instance.id,
            step_order=step_def["order"],
            approver_role=step_def.get("approver_role"),
        )
        db.add(step)

    await db.commit()
    return {"id": str(instance.id), "title": title, "status": "pending", "total_steps": len(tpl.steps)}


@router.get("/instances")
async def my_applications(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """我的申请列表"""
    from sqlalchemy import select
    from app.modules.social.oa_models import ApprovalInstance

    result = await db.execute(
        select(ApprovalInstance).where(
            ApprovalInstance.tenant_id == uuid.UUID(current_user.tenant_id),
            ApprovalInstance.applicant_id == uuid.UUID(current_user.sub),
        ).order_by(ApprovalInstance.created_at.desc())
    )
    instances = result.scalars().all()
    return [
        {"id": str(i.id), "title": i.title, "status": i.status,
         "current_step": i.current_step, "total_steps": i.total_steps,
         "created_at": i.created_at.isoformat()}
        for i in instances
    ]


@router.get("/pending")
async def pending_approvals(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """待我审批"""
    from sqlalchemy import select
    from app.modules.social.oa_models import ApprovalInstance

    result = await db.execute(
        select(ApprovalInstance).where(
            ApprovalInstance.tenant_id == uuid.UUID(current_user.tenant_id),
            ApprovalInstance.status == "pending",
        ).order_by(ApprovalInstance.created_at.desc())
    )
    instances = result.scalars().all()
    return [
        {"id": str(i.id), "title": i.title, "applicant_id": str(i.applicant_id),
         "current_step": i.current_step, "created_at": i.created_at.isoformat()}
        for i in instances
    ]


async def _verify_approver(step, current_user: TokenPayload, db) -> bool:
    """校验当前用户是否有权审批此步骤"""
    from sqlalchemy import select
    from app.modules.tenant.models import User, UserRole, Role

    # 1. 步骤必须是 pending 状态
    if step.status != "pending":
        return False

    # 2. 如果步骤指定了 approver_role，检查用户是否拥有该角色
    if step.approver_role:
        result = await db.execute(
            select(Role).join(UserRole).where(
                UserRole.user_id == uuid.UUID(current_user.sub),
                Role.name == step.approver_role,
            )
        )
        role = result.scalar_one_or_none()
        if not role:
            return False

    # 3. 检查实例状态和当前步骤
    from app.modules.social.oa_models import ApprovalInstance
    instance = await db.get(ApprovalInstance, step.instance_id)
    if not instance or instance.status != "pending":
        return False
    if step.step_order != instance.current_step + 1:
        return False  # 必须按顺序审批

    return True


@router.post("/approve/{step_id}")
@limiter.limit(RATE_OA_APPROVE)
async def approve_step(
    request: Request,
    step_id: uuid.UUID,
    comment: str | None = None,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """审批通过 (需匹配审批人角色)"""
    from app.modules.social.oa_models import ApprovalStep, ApprovalInstance

    step = await db.get(ApprovalStep, step_id)
    if not step:
        raise NotFoundException("审批步骤不存在")

    # 权限校验
    if not await _verify_approver(step, current_user, db):
        raise ForbiddenException("无审批权限：角色不匹配或非当前审批步骤")

    step.status = "approved"
    step.approver_id = uuid.UUID(current_user.sub)
    step.comment = comment

    instance = await db.get(ApprovalInstance, step.instance_id)
    if instance:
        instance.current_step = step.step_order
        if step.step_order >= instance.total_steps:
            instance.status = "approved"

    await db.commit()
    return {"step_id": str(step.id), "status": "approved", "approver": current_user.sub}


@router.post("/reject/{step_id}")
@limiter.limit(RATE_OA_APPROVE)
async def reject_step(
    request: Request,
    step_id: uuid.UUID,
    comment: str | None = None,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """审批拒绝 (需匹配审批人角色)"""
    from app.modules.social.oa_models import ApprovalStep, ApprovalInstance

    step = await db.get(ApprovalStep, step_id)
    if not step:
        raise NotFoundException("审批步骤不存在")

    if not await _verify_approver(step, current_user, db):
        raise ForbiddenException("无审批权限：角色不匹配或非当前审批步骤")

    step.status = "rejected"
    step.approver_id = uuid.UUID(current_user.sub)
    step.comment = comment

    instance = await db.get(ApprovalInstance, step.instance_id)
    if instance:
        instance.status = "rejected"

    await db.commit()
    return {"step_id": str(step.id), "status": "rejected", "approver": current_user.sub}
