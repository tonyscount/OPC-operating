"""
Skill 管理 API

GET    /skills              — Skill 列表 (Agent 发现用)
GET    /skills/{name}       — Skill 详情
POST   /skills/execute      — 执行 Skill
POST   /skills/execute/batch — 批量执行
POST   /skills/discover     — 触发自动发现
"""

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.database import get_db
from app.core.security import PermissionChecker, TokenPayload, get_current_user
from app.modules.skill.executor import executor
from app.modules.skill.registry import skill_registry
from app.modules.skill.schemas import SkillExecutionRequest, SkillExecutionResponse

router = APIRouter()
require_skill_exec = PermissionChecker("agent:execute")
require_skill_mgmt = PermissionChecker("skill:*")


async def _get_user_permissions(current_user: TokenPayload, db) -> list[str]:
    """共享依赖: 从 DB 实时查询用户权限 (避免 JWT 过期)"""
    from app.modules.tenant.service import get_user
    user = await get_user(db, uuid.UUID(current_user.tenant_id), uuid.UUID(current_user.sub))
    perms = set()
    for ur in (user.roles or []):
        perms.update(ur.role.permissions)
    return list(perms)


# ============================================================
# Skill 发现 (供 Agent 使用)
# ============================================================

@router.get("")
async def list_skills(
    current_user: TokenPayload = Depends(get_current_user),
):
    """
    获取可用 Skill 列表。

    这是 Agent 发现 Skill 的核心接口。
    LLM 通过此接口获取所有可调用工具的描述和参数，然后自主选择调用。
    """
    skills = skill_registry.list_skills()
    return {"skills": skills, "total": len(skills)}


@router.get("/for-llm")
async def list_skills_for_llm(
    current_user: TokenPayload = Depends(get_current_user),
):
    """
    获取 Skill 列表 (LLM System Prompt 格式)。

    返回纯文本，可直接拼接到 Agent 的 System Prompt 中。
    """
    return {"prompt_fragment": skill_registry.list_skills_for_llm()}


@router.get("/{skill_name}")
async def get_skill(
    skill_name: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """获取单个 Skill 的详细定义"""
    skill = skill_registry.get(skill_name)
    if not skill:
        return {"error": f"Skill '{skill_name}' 不存在"}
    return {
        "name": skill["name"],
        "display_name": skill["display_name"],
        "description": skill["description"],
        "parameters_schema": skill["parameters_schema"],
        "timeout": skill["timeout"],
        "required_permissions": skill["required_permissions"],
    }


# ============================================================
# Skill 执行
# ============================================================

@router.post("/execute", response_model=SkillExecutionResponse)
async def execute_skill(
    req: SkillExecutionRequest,
    _: bool = Depends(require_skill_exec),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    执行一个 Skill。Agent function_call 或前端直接调用。
    """
    user_permissions = await _get_user_permissions(current_user, db)
    result = await executor.execute(
        skill_name=req.skill_name,
        parameters=req.parameters,
        user_id=uuid.UUID(current_user.sub),
        tenant_id=uuid.UUID(current_user.tenant_id),
        user_permissions=user_permissions,
        trace_id=req.trace_id,
    )

    return SkillExecutionResponse(**result)


@router.post("/execute/batch")
async def execute_skills_batch(
    calls: list[SkillExecutionRequest],
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """批量并发执行多个 Skill"""
    user_permissions = await _get_user_permissions(current_user, db)
    call_dicts = [{"skill_name": c.skill_name, "parameters": c.parameters, "trace_id": c.trace_id} for c in calls]
    results = await executor.execute_batch(
        call_dicts,
        user_id=uuid.UUID(current_user.sub),
        tenant_id=uuid.UUID(current_user.tenant_id),
        user_permissions=user_permissions,
    )
    return {"results": results}


# ============================================================
# 管理操作
# ============================================================

@router.post("/discover")
async def trigger_discovery(
    current_user: TokenPayload = Depends(get_current_user),
):
    """触发 Skill 自动发现 (扫描 skills/ 目录)"""
    from app.config import settings
    count = await skill_registry.auto_discover(settings.SKILLS_DIR)
    return {"discovered": count, "total_skills": skill_registry.count}
