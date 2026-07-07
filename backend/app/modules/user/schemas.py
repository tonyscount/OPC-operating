"""用户模块 Schemas"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    """个人资料编辑"""
    display_name: str | None = Field(None, min_length=1, max_length=100)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)
    avatar_url: str | None = Field(None, max_length=500)
    bio: str | None = Field(None, max_length=500, description="个人简介")


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class PrivacySettings(BaseModel):
    """隐私设置"""
    show_email: bool = True
    show_phone: bool = False
    allow_follow: bool = True
    allow_friend_request: bool = True
    allow_search: bool = True


class UserProfileResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    org_id: UUID | None
    org_name: str | None
    username: str
    display_name: str | None
    email: str | None
    phone: str | None
    avatar_url: str | None
    bio: str | None
    status: str
    roles: list[str]
    privacy: PrivacySettings
    stats: dict  # 动态数/粉丝数/关注数
    created_at: datetime

    model_config = {"from_attributes": True}
