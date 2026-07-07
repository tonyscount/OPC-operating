"""
data_query Skill — 社群内部数据查询

零外部依赖，全部走本地数据库。
指标: member_count / new_members / popular_posts / engagement
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

logger = logging.getLogger("opc.skill.data_query")


async def data_query(
    metric: str,
    tenant_id: str,
    time_range: str = "7d",
    fmt: str = "summary",
) -> dict:
    """查询社群内部运营数据"""
    from app.core.database import async_session_factory

    days = int(time_range.replace("d", ""))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    tid = UUID(tenant_id)

    async with async_session_factory() as db:
        try:
            if metric == "member_count":
                from sqlalchemy import func, select
                from app.modules.tenant.models import User
                count = await db.scalar(
                    select(func.count(User.id)).where(
                        User.tenant_id == tid, User.is_deleted == False
                    )
                )
                return {"metric": metric, "value": count or 0,
                        "detail": f"当前社群共有 {count or 0} 名成员"}

            elif metric == "new_members":
                from sqlalchemy import func, select
                from app.modules.tenant.models import User
                count = await db.scalar(
                    select(func.count(User.id)).where(
                        User.tenant_id == tid, User.is_deleted == False,
                        User.created_at >= since,
                    )
                )
                prev_since = since - timedelta(days=days)
                prev = await db.scalar(
                    select(func.count(User.id)).where(
                        User.tenant_id == tid, User.is_deleted == False,
                        User.created_at >= prev_since, User.created_at < since,
                    )
                )
                trend = "up" if count > (prev or 0) else "down" if count < (prev or 0) else "flat"
                trend_cn = {"up": "增长", "down": "下降", "flat": "持平"}
                return {
                    "metric": metric, "time_range": time_range,
                    "value": count or 0, "trend": trend,
                    "previous_period": prev or 0,
                    "detail": f"最近{days}天新增 {count or 0} 人，较上周期{trend_cn.get(trend, '持平')}"
                }

            elif metric == "popular_posts":
                from sqlalchemy import func, select
                from app.modules.social.models import SocialPost
                result = await db.execute(
                    select(SocialPost.content, SocialPost.like_count, SocialPost.comment_count)
                    .where(SocialPost.tenant_id == tid, SocialPost.is_deleted == False,
                           SocialPost.created_at >= since)
                    .order_by((func.coalesce(SocialPost.like_count, 0) + func.coalesce(SocialPost.comment_count, 0)).desc())
                    .limit(5)
                )
                posts = []
                for p in result.all():
                    content = p[0][:120] + "..." if len(p[0] or "") > 120 else (p[0] or "")
                    posts.append({"content": content, "likes": p[1] or 0, "comments": p[2] or 0,
                                  "score": (p[1] or 0) + (p[2] or 0)})

                return {"metric": metric, "time_range": time_range,
                        "value": len(posts), "posts": posts,
                        "detail": f"最近{days}天热度最高的 {len(posts)} 条帖子"}

            elif metric == "engagement":
                from sqlalchemy import func, select
                from app.modules.social.models import SocialPost
                from app.modules.tenant.models import User
                active = await db.scalar(
                    select(func.count(func.distinct(SocialPost.author_id))).where(
                        SocialPost.tenant_id == tid, SocialPost.is_deleted == False,
                        SocialPost.created_at >= since,
                    )
                )
                total = await db.scalar(
                    select(func.count(User.id)).where(
                        User.tenant_id == tid, User.is_deleted == False,
                    )
                )
                rate = round((active or 0) / max(total or 1, 1) * 100, 1)
                return {
                    "metric": metric, "time_range": time_range,
                    "value": rate,
                    "active_users": active or 0, "total_users": total or 0,
                    "detail": f"最近{days}天互动率 {rate}%，{active or 0}/{total or 0} 名成员有发言或互动"
                }

            elif metric == "overview":
                # 综合仪表盘
                from sqlalchemy import func, select
                from app.modules.tenant.models import User
                from app.modules.social.models import SocialPost
                from app.modules.knowledge.models import KnowledgeDocument
                from app.modules.trade.models import Order

                users = await db.scalar(select(func.count(User.id)).where(User.tenant_id == tid, User.is_deleted == False))
                posts = await db.scalar(select(func.count(SocialPost.id)).where(SocialPost.tenant_id == tid, SocialPost.is_deleted == False))
                docs = await db.scalar(select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.tenant_id == tid, KnowledgeDocument.is_deleted == False))
                orders = await db.scalar(select(func.count(Order.id)).where(Order.tenant_id == tid, Order.is_deleted == False))
                new_users = await db.scalar(
                    select(func.count(User.id)).where(User.tenant_id == tid, User.is_deleted == False, User.created_at >= since))

                return {
                    "metric": "overview", "time_range": time_range,
                    "members": users or 0, "posts": posts or 0,
                    "documents": docs or 0, "orders": orders or 0,
                    "new_members_this_period": new_users or 0,
                    "detail": f"社群总览: {users or 0}成员 · {posts or 0}动态 · {docs or 0}文档"
                }

            elif metric == "trend":
                # 近 N 天每日数据趋势
                from sqlalchemy import func, select, text as sqltxt
                daily_data = []
                for d in range(days - 1, -1, -1):
                    day_start = (datetime.now(timezone.utc) - timedelta(days=d)).replace(hour=0, minute=0, second=0, microsecond=0)
                    day_end = day_start + timedelta(days=1)
                    posts_count = await db.scalar(
                        select(func.count(SocialPost.id)).where(
                            SocialPost.tenant_id == tid, SocialPost.is_deleted == False,
                            SocialPost.created_at >= day_start, SocialPost.created_at < day_end,
                        )
                    ) or 0
                    new_users_count = await db.scalar(
                        select(func.count(User.id)).where(
                            User.tenant_id == tid, User.is_deleted == False,
                            User.created_at >= day_start, User.created_at < day_end,
                        )
                    ) or 0
                    daily_data.append({
                        "date": day_start.strftime("%m/%d"),
                        "day": day_start.strftime("%a"),
                        "posts": posts_count,
                        "new_users": new_users_count,
                    })
                return {"metric": metric, "time_range": time_range, "data": daily_data,
                        "detail": f"近{days}天趋势"}

            else:
                return {
                    "error": f"不支持的指标: {metric}",
                    "supported": ["member_count", "new_members", "popular_posts", "engagement", "overview", "trend"]
                }

        except Exception as e:
            logger.error(f"data_query failed: {e}")
            return {"error": f"查询失败: {str(e)}", "metric": metric}
