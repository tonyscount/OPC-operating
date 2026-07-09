"""
社交模块数据模型

- 动态发布 (Post)
- 评论 (Comment)
- 点赞 (Like)
- 关注关系 (Follow)
- 好友关系 (Friend)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import TenantBase, UUIDMixin, TimestampMixin, Base


class SocialPost(TenantBase):
    __tablename__ = "social_posts"

    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_urls: Mapped[list[str] | None] = mapped_column(
        "media_urls", String(1000), nullable=True, comment="JSON 数组字符串"
    )
    circle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_circles.id", ondelete="SET NULL"), nullable=True,
        comment="所属圈子 (空=全局动态)"
    )
    visibility: Mapped[str] = mapped_column(
        String(20), default="public", comment="public/org_only/private"
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, comment="置顶")
    is_essence: Mapped[bool] = mapped_column(Boolean, default=False, comment="精华")
    view_count: Mapped[int] = mapped_column(default=0)
    like_count: Mapped[int] = mapped_column(default=0)
    comment_count: Mapped[int] = mapped_column(default=0)

    # 关系
    comments: Mapped[list["SocialComment"]] = relationship(back_populates="post")


class SocialComment(TenantBase):
    __tablename__ = "social_comments"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_posts.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_comments.id", ondelete="CASCADE")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 关系
    post: Mapped["SocialPost"] = relationship(back_populates="comments")
    replies: Mapped[list["SocialComment"]] = relationship(
        "SocialComment", back_populates="parent", remote_side="SocialComment.id"
    )
    parent: Mapped["SocialComment | None"] = relationship(
        "SocialComment", remote_side="SocialComment.parent_id", back_populates="replies"
    )


class SocialLike(TenantBase):
    __tablename__ = "social_likes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="post / comment"
    )
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class UserFollow(TenantBase):
    """关注关系 (A关注B) — created_at 继承自 TimestampMixin"""
    __tablename__ = "user_follows"

    follower_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    following_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


class UserFriend(TenantBase):
    """好友关系 (双向确认)"""
    __tablename__ = "user_friends"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    friend_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", comment="pending/accepted/rejected"
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
