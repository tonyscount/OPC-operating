"""数据清理任务 — 清理过期 Token、旧日志"""

import logging
from datetime import datetime, timedelta, timezone

from worker.celery_app import celery_app

logger = logging.getLogger("opc.tasks.data_cleanup")


@celery_app.task(bind=True, max_retries=2)
def run(self):
    """清理过期数据: 黑名单 Token、Refresh Token、旧登录日志"""
    from app.config import settings
    from sqlalchemy import create_engine, text

    engine = create_engine(settings.DATABASE_URL_SYNC)
    deleted_total = 0

    with engine.connect() as conn:
        # 1. 清理过期 Token 黑名单
        result = conn.execute(
            text("DELETE FROM token_blacklist WHERE expires_at < :now"),
            {"now": datetime.now(timezone.utc)},
        )
        deleted_total += result.rowcount
        logger.info(f"Cleaned {result.rowcount} expired blacklist tokens")

        # 2. 清理过期 Refresh Token
        result = conn.execute(
            text("DELETE FROM refresh_tokens WHERE expires_at < :now OR revoked = true"),
            {"now": datetime.now(timezone.utc)},
        )
        deleted_total += result.rowcount
        logger.info(f"Cleaned {result.rowcount} revoked/expired refresh tokens")

        # 3. 清理 90 天前的登录日志
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        result = conn.execute(
            text("DELETE FROM login_logs WHERE created_at < :cutoff"),
            {"cutoff": cutoff},
        )
        deleted_total += result.rowcount
        logger.info(f"Cleaned {result.rowcount} old login logs")

        conn.commit()

    return {"status": "ok", "deleted_total": deleted_total}
