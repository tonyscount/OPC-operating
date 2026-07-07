"""
多租户管理 API

所有接口都需要管理员权限，且操作范围限定在当前用户所属租户内。
"""

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.database import get_db
from app.core.security import PermissionChecker, TokenPayload, get_current_user
from app.modules.tenant import service as tenant_svc
from app.modules.tenant.schemas import (
    OrgCreate,
    OrgResponse,
    OrgUpdate,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    TenantResponse,
    TenantUpdate,
    UserCreate,
    UserListParams,
    UserResponse,
    UserUpdate,
)

router = APIRouter()

require_tenant_mgmt = PermissionChecker("tenant:manage")
require_org_mgmt = PermissionChecker("org:manage")
require_user_mgmt = PermissionChecker("user:manage")
require_role_mgmt = PermissionChecker("role:manage")


# ============================================================
# 租户
# ============================================================

@router.get("/info", response_model=TenantResponse)
async def get_my_tenant(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取当前用户所属租户信息"""
    return await tenant_svc.get_tenant(db, uuid.UUID(current_user.tenant_id))


@router.patch("/info", response_model=TenantResponse)
async def update_my_tenant(
    data: TenantUpdate,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """更新当前租户信息 (需管理员权限)"""
    return await tenant_svc.update_tenant(
        db,
        uuid.UUID(current_user.tenant_id),
        **data.model_dump(exclude_none=True),
    )


# ============================================================
# 组织/部门
# ============================================================

@router.post("/orgs", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_org(
    data: OrgCreate, _: bool = Depends(require_org_mgmt),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """创建组织/部门"""
    return await tenant_svc.create_org(
        db,
        tenant_id=uuid.UUID(current_user.tenant_id),
        **data.model_dump(),
    )


@router.get("/orgs", response_model=list[OrgResponse])
async def list_orgs(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取组织树"""
    return await tenant_svc.get_org_tree(db, uuid.UUID(current_user.tenant_id))


@router.patch("/orgs/{org_id}", response_model=OrgResponse)
async def update_org(
    org_id: uuid.UUID,
    data: OrgUpdate,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """更新组织信息"""
    return await tenant_svc.update_org(
        db, uuid.UUID(current_user.tenant_id), org_id,
        **data.model_dump(exclude_none=True),
    )


@router.delete("/orgs/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org(
    org_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """删除组织 (前提: 无子组织、无成员)"""
    await tenant_svc.delete_org(db, uuid.UUID(current_user.tenant_id), org_id)


@router.get("/orgs/{org_id}/members", response_model=dict)
async def get_org_members(
    org_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取组织成员列表"""
    users, total = await tenant_svc.get_org_members(
        db, uuid.UUID(current_user.tenant_id), org_id, page=page, page_size=page_size,
    )
    return {
        "items": [UserResponse.model_validate(u) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============================================================
# 用户 (管理端)
# ============================================================

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate, _: bool = Depends(require_user_mgmt),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """创建用户并分配角色"""
    return await tenant_svc.create_user(
        db,
        tenant_id=uuid.UUID(current_user.tenant_id),
        **data.model_dump(),
    )


@router.get("/users", response_model=dict)
async def list_users(
    keyword: str | None = None,
    org_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """用户列表 (支持搜索、按部门/状态筛选、分页)"""
    users, total = await tenant_svc.list_users(
        db, uuid.UUID(current_user.tenant_id),
        keyword=keyword, org_id=org_id, status=status,
        page=page, page_size=page_size,
    )
    return {
        "items": [UserResponse.model_validate(u) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取用户详情"""
    return await tenant_svc.get_user(db, uuid.UUID(current_user.tenant_id), user_id)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """更新用户信息"""
    return await tenant_svc.update_user(
        db, uuid.UUID(current_user.tenant_id), user_id,
        **data.model_dump(exclude_none=True),
    )


@router.post("/users/{user_id}/roles", response_model=UserResponse)
async def assign_user_roles(
    user_id: uuid.UUID,
    role_ids: list[uuid.UUID],
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """为用户重新分配角色"""
    return await tenant_svc.assign_roles(
        db, uuid.UUID(current_user.tenant_id), user_id, role_ids,
    )


# ============================================================
# 角色
# ============================================================

@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    data: RoleCreate, _: bool = Depends(require_role_mgmt),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """创建自定义角色"""
    return await tenant_svc.create_role(
        db, uuid.UUID(current_user.tenant_id), **data.model_dump(),
    )


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取角色列表"""
    return await tenant_svc.list_roles(db, uuid.UUID(current_user.tenant_id))


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: uuid.UUID,
    data: RoleUpdate,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """更新角色 (含权限列表)"""
    return await tenant_svc.update_role(
        db, uuid.UUID(current_user.tenant_id), role_id,
        **data.model_dump(exclude_none=True),
    )


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """删除自定义角色 (系统角色不可删)"""
    await tenant_svc.delete_role(db, uuid.UUID(current_user.tenant_id), role_id)


# ============================================================
# 权限列表 (只读)
# ============================================================

AVAILABLE_PERMISSIONS = [
    # 租户管理
    "tenant:manage",
    # 组织
    "org:manage",
    # 用户
    "user:manage", "user:read",
    # 角色
    "role:manage",
    # 知识库
    "knowledge:read", "knowledge:upload", "knowledge:delete", "knowledge:*",
    # Agent
    "agent:execute", "agent:manage", "agent:*",
    # Skill
    "skill:*",
    # 搜索
    "search:read",
    # 社交
    "social:read", "social:write", "social:*",
    # 定时任务
    "schedule:read", "schedule:manage",
    # 交易
    "trade:read", "trade:write", "trade:*",
    # 通知
    "notification:send",
]


@router.get("/permissions")
async def list_permissions():
    """获取系统中所有可用的权限标识列表"""
    return {"permissions": AVAILABLE_PERMISSIONS}
