"""认证模块 Schemas"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    tenant_slug: str = Field(description="租户唯一标识")
    username: str
    password: str


class RegisterRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=200, description="租户/企业名称")
    tenant_slug: str = Field(
        min_length=2, max_length=50,
        pattern=r"^[a-z0-9-]+$",
        description="租户标识 (URL 安全，创建后不可改)",
    )
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    email: str | None = None
    display_name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class UserInfo(BaseModel):
    user_id: str
    tenant_id: str
    tenant_name: str
    org_id: str | None
    username: str
    display_name: str | None
    email: str | None
    avatar_url: str | None
    roles: list[str]
    permissions: list[str]
