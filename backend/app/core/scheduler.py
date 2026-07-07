"""
轻量任务调度 — 不需要 Redis，单进程 asyncio。

每天 8:00 触发保鲜检查 + 简报生成。
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger("opc.scheduler")


async def run_daily_tasks():
    """手动或定时触发的每日任务"""
    import asyncio as _asyncio

    async def freshness():
        try:
            from worker.tasks.freshness_check import run
            result = run()  # Celery task 也能直接调
            logger.info(f"Freshness check: {result}")
        except Exception as e:
            logger.error(f"Freshness check failed: {e}")

    async def briefing():
        try:
            from worker.tasks.daily_briefing import run
            result = run()
            logger.info(f"Daily briefing: {result}")
        except Exception as e:
            logger.error(f"Daily briefing failed: {e}")

    await _asyncio.gather(freshness(), briefing())


def start_scheduler():
    """启动后台调度器 (开发环境用 asyncio loop，生产用 Celery)"""
    logger.info("Scheduler: async mode (no Redis). Call run_daily_tasks() manually or via cron.")
    # 如果系统有 Redis，自动切 Celery
    try:
        import redis
        r = redis.from_url("redis://localhost:6379/0")
        r.ping()
        logger.info("Scheduler: Redis available, use Celery Beat for production scheduling")
        return
    except Exception:
        pass

    logger.info("Scheduler: Use system cron or manual trigger for daily tasks")
