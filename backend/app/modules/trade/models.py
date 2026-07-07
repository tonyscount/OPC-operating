"""
交易模块数据模型

- Product: 商品/服务
- Order: 订单
- OrderItem: 订单项
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import TenantBase


class Product(TenantBase):
    """商品/服务"""
    __tablename__ = "trade_products"

    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="goods/service/digital"
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, comment="库存 (-1=无限)")
    images: Mapped[list[str] | None] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(
        String(20), default="published", comment="draft/published/sold_out/removed"
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    order_count: Mapped[int] = mapped_column(Integer, default=0)


class Order(TenantBase):
    """订单"""
    __tablename__ = "trade_orders"

    buyer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending",
        comment="pending/paid/shipping/completed/cancelled/refunded",
    )
    payment_method: Mapped[str | None] = mapped_column(String(50))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remark: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan",
    )


class OrderItem(TenantBase):
    """订单项"""
    __tablename__ = "trade_order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trade_orders.id", ondelete="CASCADE"), nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trade_products.id", ondelete="SET NULL"), nullable=True,
    )
    product_title: Mapped[str] = mapped_column(String(500), nullable=False, comment="快照: 商品名")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
