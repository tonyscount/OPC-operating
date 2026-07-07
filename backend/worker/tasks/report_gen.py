"""报表生成任务 — 日报/周报"""

import logging
from datetime import datetime, timedelta, timezone

from worker.celery_app import celery_app

logger = logging.getLogger("opc.tasks.report_gen")


def _query_stats(tenant_filter: str = "") -> dict:
    """汇总昨日关键指标"""
    from app.config import settings
    from sqlalchemy import create_engine, text

    engine = create_engine(settings.DATABASE_URL_SYNC)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    stats = {}
    with engine.connect() as conn:
        # 新增用户
        stats["new_users"] = conn.execute(
            text("SELECT COUNT(*) FROM users WHERE created_at >= :d"),
            {"d": yesterday.replace(hour=0, minute=0, second=0)},
        ).scalar() or 0

        # 新增动态
        stats["new_posts"] = conn.execute(
            text("SELECT COUNT(*) FROM social_posts WHERE created_at >= :d AND is_deleted = false"),
            {"d": yesterday.replace(hour=0, minute=0, second=0)},
        ).scalar() or 0

        # 新增文档
        stats["new_documents"] = conn.execute(
            text("SELECT COUNT(*) FROM knowledge_documents WHERE created_at >= :d AND is_deleted = false"),
            {"d": yesterday.replace(hour=0, minute=0, second=0)},
        ).scalar() or 0

        # 新增订单
        stats["new_orders"] = conn.execute(
            text("SELECT COUNT(*) FROM trade_orders WHERE created_at >= :d AND is_deleted = false"),
            {"d": yesterday.replace(hour=0, minute=0, second=0)},
        ).scalar() or 0

        # 登录人次
        stats["logins"] = conn.execute(
            text("SELECT COUNT(*) FROM login_logs WHERE created_at >= :d AND success = true"),
            {"d": yesterday.replace(hour=0, minute=0, second=0)},
        ).scalar() or 0

    return stats


@celery_app.task(bind=True, max_retries=2)
def run_daily(self):
    """生成日报"""
    logger.info("Generating daily report...")
    stats = _query_stats()

    # 飞书通知
    from app.config import settings
    if settings.FEISHU_WEBHOOK_URL:
        import json, urllib.request
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        text = (
            f"📊 OPC 日报 ({yesterday})\n"
            f"新增用户: {stats['new_users']}\n"
            f"新增动态: {stats['new_posts']}\n"
            f"新增文档: {stats['new_documents']}\n"
            f"新增订单: {stats['new_orders']}\n"
            f"登录人次: {stats['logins']}"
        )
        payload = json.dumps({"msg_type": "text", "content": {"text": text}}).encode()
        try:
            req = urllib.request.Request(settings.FEISHU_WEBHOOK_URL, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    logger.info(f"Daily report: {stats}")
    return {"status": "ok", "report_type": "daily", "stats": stats}


@celery_app.task(bind=True, max_retries=2)
def run_weekly(self):
    """生成周报"""
    logger.info("Generating weekly report...")
    return {"status": "ok", "report_type": "weekly"}
