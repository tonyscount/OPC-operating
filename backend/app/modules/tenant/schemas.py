"""
多租户模块 — Pydantic Schemas
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ========== 租户 ==========
class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200, description="租户名称")
    slug: str = Field(
        min_length=2,
        max_length=50,
        pattern=r"^[a-z0-9-]+$",
        description="唯一标识 (URL 安全)",
    )
    plan: str = Field(default="free", pattern="^(free|pro|enterprise)$")


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    plan: str | None = Field(None, pattern="^(free|pro|enterprise)$")
    status: str | None = Field(None, pattern="^(active|suspended)$")


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    plan: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ========== 组织 ==========
class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    parent_id: UUID | None = None
    sort_order: int = 0


class OrgUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    parent_id: UUID | None = None
    sort_order: int | None = None


class OrgResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    parent_id: UUID | None
    name: str
    code: str | None
    sort_order: int
    children: list["OrgResponse"] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ========== 用户 ==========
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    email: str | None = None
    phone: str | None = None
    display_name: str | None = None
    org_id: UUID | None = None
    role_ids: list[UUID] = []


class UserUpdate(BaseModel):
    email: str | None = None
    phone: str | None = None
    display_name: str | None = None
    org_id: UUID | None = None
    status: str | None = Field(None, pattern="^(active|disabled|banned)$")


class UserResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    org_id: UUID | None
    username: str
    email: str | None
    phone: str | None
    display_name: str | None
    avatar_url: str | None
    status: str
    roles: list["RoleBrief"] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListParams(BaseModel):
    """用户列表查询参数"""
    page: int = 1
    page_size: int = 20
    keyword: str | None = None  # 搜索用户名/邮箱/手机
    org_id: UUID | None = None  # 按部门筛选
    status: str | None = None


# ========== 角色 ==========
class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    permissions: list[str] = Field(
        default_factory=list,
        description="权限标识列表，如 ['knowledge:upload', 'user:manage']",
    )


class RoleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    permissions: list[str] | None = None


class RoleBrief(BaseModel):
    id: UUID
    name: str

    model_config = {"from_attributes": True}


class RoleResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    permissions: list[str]
    is_system: bool
    created_at: datetime

    model_config = {"from_attributes": True}
