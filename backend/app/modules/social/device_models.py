"""
设备 & 工程师 IP 相关模型

- Device: OPC 设备资产
- UserStatus: 用户当前状态 (类似微信状态/Soul瞬间)
- UserSkill: 工程师技能标签
- Greet: 打招呼记录
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import TenantBase, UUIDMixin, TimestampMixin, Base


class Device(TenantBase):
    """OPC 设备资产"""
    __tablename__ = "devices"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="设备名称")
    device_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="opc_gateway/plc/sensor/camera/other"
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), comment="IP 地址")
    port: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(500), comment="地理位置描述")
    latitude: Mapped[float | None] = mapped_column(Float, comment="纬度")
    longitude: Mapped[float | None] = mapped_column(Float, comment="经度")
    status: Mapped[str] = mapped_column(
        String(20), default="offline", comment="online/offline/warning/error"
    )
    last_online_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    image_url: Mapped[str | None] = mapped_column(String(500), comment="设备图片")
    specs: Mapped[dict | None] = mapped_column(JSONB, comment="技术参数")
    tags: Mapped[list[str] | None] = mapped_column(JSONB, default=list, comment="设备标签")
    view_count: Mapped[int] = mapped_column(Integer, default=0)


class UserStatus(UUIDMixin, TimestampMixin, Base):
    """用户当前状态 (类似微信状态，24h 后过期)"""
    __tablename__ = "user_statuses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
    )
    emoji: Mapped[str | None] = mapped_column(String(10), comment="状态表情")
    text: Mapped[str] = mapped_column(String(100), nullable=False, comment="状态文字")
    background_url: Mapped[str | None] = mapped_column(String(500))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="过期时间")


class UserSkill(TenantBase):
    """工程师技能标签"""
    __tablename__ = "user_skills"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="技能名称")
    category: Mapped[str | None] = mapped_column(String(50), comment="protocol/software/hardware/certification")
    level: Mapped[str | None] = mapped_column(String(20), default="intermediate", comment="beginner/intermediate/expert/master")
    endorsed_count: Mapped[int] = mapped_column(Integer, default=0)


class Greet(UUIDMixin, TimestampMixin, Base):
    """打招呼记录 (类似陌陌的 Hi)"""
    __tablename__ = "greets"

    from_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    to_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
    )
    message: Mapped[str | None] = mapped_column(String(200), comment="打招呼内容")
    status: Mapped[str] = mapped_column(
        String(20), default="pending", comment="pending/accepted/ignored"
    )
    source: Mapped[str | None] = mapped_column(String(50), comment="lbs/feed/profile/search")
    latitude: Mapped[float | None] = mapped_column(Float, comment="打招呼时的纬度")
    longitude: Mapped[float | None] = mapped_column(Float, comment="打招呼时的经度")
