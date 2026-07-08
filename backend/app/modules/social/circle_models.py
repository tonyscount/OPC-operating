"""
圈子模型 — OPC 社区体系核心

Circle: 技能/行业圈子 (类似贴吧的"吧")
CircleMember: 圈子成员关系
SocialPost 通过 circle_id FK 关联 (可选 — 不属于圈子就是全局动态)
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import TenantBase


class Circle(TenantBase):
    """技能/行业圈子"""
    __tablename__ = "social_circles"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(
        String(30), default="general",
        comment="ops/hardware/automation/business/other"
    )
    icon_url: Mapped[str | None] = mapped_column(String(500))
    cover_url: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    member_count: Mapped[int] = mapped_column(Integer, default=1)
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)

    members: Mapped[list["CircleMember"]] = relationship(
        back_populates="circle", cascade="all, delete-orphan", lazy="selectin",
    )


class CircleMember(TenantBase):
    """圈子成员"""
    __tablename__ = "social_circle_members"

    circle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_circles.id", ondelete="CASCADE"), nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(20), default="member", comment="owner/admin/member"
    )

    circle: Mapped["Circle"] = relationship(back_populates="members")
