"""
多租户 & 组织模型

架构:
    Tenant (租户/企业)
      └── Organization (组织/部门，树形结构)
            └── User (用户，关联 org)
                  └── UserRole → Role (角色 & 权限)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin


# ========== 租户 ==========
class Tenant(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="租户名称")
    slug: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="租户唯一标识 (URL 安全)"
    )
    plan: Mapped[str] = mapped_column(
        String(20), default="free", comment="套餐: free/pro/enterprise"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="状态: active/suspended/deleted"
    )
    config: Mapped[dict] = mapped_column(
        JSONB, default=dict, comment="租户自定义配置"
    )

    # 关系
    organizations: Mapped[list["Organization"]] = relationship(
        back_populates="tenant", lazy="selectin"
    )
    users: Mapped[list["User"]] = relationship(back_populates="tenant", lazy="selectin")


# ========== 组织 (树形) ==========
class Organization(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "organizations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="上级组织 ID (树形结构)",
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=True, comment="组织编码")
    sort_order: Mapped[int] = mapped_column(default=0, comment="排序")

    # 关系
    tenant: Mapped["Tenant"] = relationship(back_populates="organizations")
    parent: Mapped["Organization | None"] = relationship(
        "Organization", remote_side="Organization.id", back_populates="children"
    )
    children: Mapped[list["Organization"]] = relationship(
        "Organization", back_populates="parent", lazy="selectin",
    )
    users: Mapped[list["User"]] = relationship(back_populates="organization")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_org_code_per_tenant"),
    )


# ========== 用户 ==========
class User(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL")
    )
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="active/disabled/banned"
    )

    # 关系
    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    organization: Mapped["Organization"] = relationship(back_populates="users")
    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_username_per_tenant"),
    )


# ========== 角色 & 权限 ==========
class Role(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    permissions: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        comment="权限列表，如 ['knowledge:upload', 'agent:execute', 'user:manage']",
    )
    is_system: Mapped[bool] = mapped_column(
        default=False, comment="是否为系统内置角色 (不可删除)"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_role_name_per_tenant"),
    )


class UserRole(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="roles")
    role: Mapped["Role"] = relationship(lazy="selectin")

    @property
    def name(self) -> str:
        """委托 role.name，兼容 Pydantic from_attributes 校验"""
        return self.role.name if self.role else ""

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )
