"""
运营后台 API (管理端)

GET  /ops/dashboard          — 运营仪表盘
GET  /ops/users/stats        — 用户统计
GET  /ops/content/stats      — 内容统计
GET  /ops/reports/daily      — 日报
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.database import get_db
from app.core.security import PermissionChecker, TokenPayload, get_current_user

router = APIRouter()
require_ops = PermissionChecker("ops:*")


@router.get("/dashboard")
async def dashboard(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """运营仪表盘 — 核心指标汇总"""
    from app.modules.tenant.models import User
    from app.modules.social.models import SocialPost
    from app.modules.knowledge.models import KnowledgeDocument
    from app.modules.trade.models import Order

    tid = uuid.UUID(current_user.tenant_id)

    # 用户数
    user_count = await db.scalar(
        select(func.count(User.id)).where(User.tenant_id == tid, User.is_deleted == False)
    )
    # 动态数
    post_count = await db.scalar(
        select(func.count(SocialPost.id)).where(SocialPost.tenant_id == tid, SocialPost.is_deleted == False)
    )
    # 文档数
    doc_count = await db.scalar(
        select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.tenant_id == tid, KnowledgeDocument.is_deleted == False)
    )
    # 订单数
    order_count = await db.scalar(
        select(func.count(Order.id)).where(Order.tenant_id == tid, Order.is_deleted == False)
    )

    return {
        "users": user_count or 0,
        "posts": post_count or 0,
        "documents": doc_count or 0,
        "orders": order_count or 0,
    }


@router.get("/users/stats")
async def user_stats(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """用户统计 — 日活/周活/月活 (简化版)"""
    from app.modules.tenant.models import User
    from app.modules.auth.models import LoginLog
    from datetime import datetime, timedelta, timezone

    tid = uuid.UUID(current_user.tenant_id)
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0)

    total_users = await db.scalar(
        select(func.count(User.id)).where(User.tenant_id == tid)
    )
    today_logins = await db.scalar(
        select(func.count(LoginLog.id)).where(
            LoginLog.tenant_id == tid, LoginLog.success == True,
            LoginLog.created_at >= today,
        )
    )

    return {
        "total_users": total_users or 0,
        "today_logins": today_logins or 0,
    }


@router.get("/content/stats")
async def content_stats(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """内容统计"""
    from app.modules.social.models import SocialPost, SocialComment, SocialLike
    from datetime import datetime, timedelta, timezone

    tid = uuid.UUID(current_user.tenant_id)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    week_posts = await db.scalar(
        select(func.count(SocialPost.id)).where(
            SocialPost.tenant_id == tid, SocialPost.created_at >= week_ago,
        )
    )
    return {"posts_this_week": week_posts or 0}
