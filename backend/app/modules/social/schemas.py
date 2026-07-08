"""社交模块 — Pydantic Schemas"""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# HTML 标签清洗 (XSS 防护)。TODO: 未来支持 Markdown/富文本时需替换为白名单方案
_HTML_TAG_RE = re.compile(r"<[^>]*>")


def strip_html(text: str) -> str:
    """移除所有 HTML 标签，防止 XSS"""
    return _HTML_TAG_RE.sub("", text)


# ============================================================
# 动态 (Post)
# ============================================================
class PostCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000, description="动态内容")
    media_urls: list[str] | None = Field(None, max_length=9, description="图片/视频 URL 列表")
    visibility: str = Field(default="public", pattern="^(public|org_only|private)$")

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        return strip_html(v)


class PostUpdate(BaseModel):
    content: str | None = Field(None, min_length=1, max_length=5000)
    visibility: str | None = Field(None, pattern="^(public|org_only|private)$")

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str | None) -> str | None:
        return strip_html(v) if v is not None else None


class AuthorBrief(BaseModel):
    id: UUID
    username: str
    display_name: str | None
    avatar_url: str | None

    model_config = {"from_attributes": True}


class PostResponse(BaseModel):
    id: UUID
    author: AuthorBrief | None = None  # 需要 JOIN 填充
    content: str
    media_urls: list[str] | None
    visibility: str
    view_count: int
    like_count: int
    comment_count: int
    is_liked: bool = False  # 当前用户是否已点赞
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PostListParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=50)
    feed_type: str = Field(default="all", pattern="^(all|following|user)$")
    user_id: UUID | None = None  # feed_type=user 时指定用户


# ============================================================
# 评论
# ============================================================
class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    parent_id: UUID | None = None  # 回复某条评论

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        return strip_html(v)


class CommentResponse(BaseModel):
    id: UUID
    post_id: UUID
    author: AuthorBrief | None = None
    parent_id: UUID | None
    content: str
    replies: list["CommentResponse"] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# 点赞
# ============================================================
class LikeResponse(BaseModel):
    id: UUID
    user_id: UUID
    target_type: str
    target_id: UUID


# ============================================================
# 关注
# ============================================================
class FollowResponse(BaseModel):
    id: UUID
    follower_id: UUID
    following_id: UUID
    created_at: datetime


# ============================================================
# 好友
# ============================================================
class FriendRequest(BaseModel):
    friend_id: UUID
    message: str | None = Field(None, max_length=200, description="好友申请附言")


class FriendResponse(BaseModel):
    id: UUID
    user_id: UUID
    friend_id: UUID
    status: str
    user_info: AuthorBrief | None = None
    friend_info: AuthorBrief | None = None
    created_at: datetime
    accepted_at: datetime | None

    model_config = {"from_attributes": True}


# ============================================================
# 用户搜索
# ============================================================
class UserSearchResult(BaseModel):
    id: UUID
    username: str
    display_name: str | None
    avatar_url: str | None
    org_name: str | None
    is_following: bool = False
    is_friend: bool = False

    model_config = {"from_attributes": True}
