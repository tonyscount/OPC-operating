"""
交易 API

POST   /trade/products          — 发布商品
GET    /trade/products          — 商品列表
GET    /trade/products/{id}     — 商品详情
PATCH  /trade/products/{id}     — 编辑商品
DELETE /trade/products/{id}     — 下架商品
POST   /trade/orders            — 创建订单
GET    /trade/orders            — 我的订单
GET    /trade/orders/{id}       — 订单详情
PATCH  /trade/orders/{id}       — 更新订单状态
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from app.core.database import get_db
from app.core.security import PermissionChecker, TokenPayload, get_current_user
from app.modules.trade.models import Order, OrderItem, Product

router = APIRouter()
require_trade_read = PermissionChecker("trade:read")
require_trade_write = PermissionChecker("trade:write")


@router.post("/products", status_code=status.HTTP_201_CREATED)
async def create_product(
    title: str, price: float, category: str = "goods",
    description: str | None = None, stock: int = 1, images: list[str] | None = None,
    _: bool = Depends(require_trade_write),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """发布商品"""
    from decimal import Decimal
    product = Product(
        tenant_id=uuid.UUID(current_user.tenant_id),
        seller_id=uuid.UUID(current_user.sub),
        title=title, description=description, category=category,
        price=Decimal(str(price)), stock=stock, images=images or [],
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return {"id": str(product.id), "title": product.title, "price": float(product.price)}


@router.get("/products")
async def list_products(
    category: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """商品列表"""
    conditions = [Product.tenant_id == uuid.UUID(current_user.tenant_id), Product.status == "published"]
    if category:
        conditions.append(Product.category == category)
    if keyword:
        conditions.append(Product.title.ilike(f"%{keyword}%"))

    total = await db.scalar(select(func.count(Product.id)).where(*conditions))
    result = await db.execute(
        select(Product).where(*conditions)
        .order_by(Product.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    products = result.scalars().all()
    items = [{"id": str(p.id), "title": p.title, "price": float(p.price),
              "category": p.category, "stock": p.stock, "order_count": p.order_count} for p in products]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/products/{product_id}")
async def get_product(
    product_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """商品详情"""
    product = await db.get(Product, product_id)
    if not product or product.tenant_id != uuid.UUID(current_user.tenant_id):
        return {"error": "商品不存在"}
    return {"id": str(product.id), "title": product.title, "description": product.description,
            "price": float(product.price), "stock": product.stock, "images": product.images,
            "category": product.category, "seller_id": str(product.seller_id)}


@router.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_order(
    items: list[dict],  # [{product_id, quantity}]
    _: bool = Depends(require_trade_write),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """创建订单"""
    from decimal import Decimal
    total = Decimal("0")
    order_items = []

    for item_data in items:
        product = await db.get(Product, uuid.UUID(item_data["product_id"]))
        if not product or product.status != "published":
            return {"error": f"商品 {item_data['product_id']} 不存在或已下架"}
        quantity = min(item_data.get("quantity", 1), product.stock if product.stock > 0 else 999)
        item_total = product.price * quantity
        total += item_total
        order_items.append({
            "product_id": product.id, "product_title": product.title,
            "quantity": quantity, "unit_price": product.price,
        })

    order = Order(
        tenant_id=uuid.UUID(current_user.tenant_id),
        buyer_id=uuid.UUID(current_user.sub),
        total_amount=total, status="pending",
    )
    db.add(order)
    await db.flush()

    for oi in order_items:
        db.add(OrderItem(
            tenant_id=uuid.UUID(current_user.tenant_id),
            order_id=order.id, **oi,
        ))

    await db.commit()
    return {"id": str(order.id), "total_amount": float(total), "item_count": len(order_items), "status": "pending"}


@router.get("/orders")
async def my_orders(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """我的订单"""
    result = await db.execute(
        select(Order).where(
            Order.tenant_id == uuid.UUID(current_user.tenant_id),
            Order.buyer_id == uuid.UUID(current_user.sub),
        ).order_by(Order.created_at.desc()).limit(50)
    )
    orders = result.scalars().all()
    return [{"id": str(o.id), "total_amount": float(o.total_amount),
             "status": o.status, "created_at": o.created_at.isoformat()} for o in orders]
