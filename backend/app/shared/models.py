"""
共享基础模型。

所有业务模型继承 Base，自动获得:
- id: UUID 主键
- created_at / updated_at: 时间戳
- tenant_id: 租户隔离外键
- soft_delete: 软删除标记
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ========== 声明式基类 ==========
class Base(DeclarativeBase):
    pass


# ========== 通用 Mixin ==========
class UUIDMixin:
    """UUID 主键"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )


class TimestampMixin:
    """创建 & 更新时间"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SoftDeleteMixin:
    """软删除"""
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TenantMixin:
    """租户隔离 —— 所有业务表必备"""
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


# ========== 完整基类 (常用组合) ==========
class TenantBase(UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin, Base):
    """
    标准业务表基类 = UUID主键 + 时间戳 + 软删除 + 租户隔离

    用法:
        class SocialPost(TenantBase):
            __tablename__ = "social_posts"
            content: Mapped[str] = ...
    """

    __abstract__ = True
