"""
Celery Beat 动态调度 — 从数据库加载定时任务配置。

管理面板创建/更新的 ScheduleTask 会自动同步到 Celery Beat。
"""

import logging

from app.config import settings

logger = logging.getLogger("opc.beat")


def load_dynamic_schedule() -> dict:
    """
    从 schedule_tasks 表加载启用的任务，转换为 Celery Beat schedule 格式。

    Celery Beat 会在启动时调用此函数。
    """
    try:
        from sqlalchemy import create_engine, select, text
        from app.modules.schedule.models import ScheduleTask

        engine = create_engine(settings.DATABASE_URL_SYNC)
        schedule = {}

        with engine.connect() as conn:
            tasks = conn.execute(
                select(ScheduleTask).where(ScheduleTask.enabled == True)
            ).all()

            for task in tasks:
                # 解析 cron 表达式 "分 时 日 月 周"
                parts = task.cron_expression.strip().split()
                if len(parts) != 5:
                    logger.warning(f"Invalid cron: {task.cron_expression} for {task.task_key}")
                    continue

                minute, hour, dom, month, dow = parts
                from celery.schedules import crontab

                schedule[task.task_key] = {
                    "task": task.task_key,
                    "schedule": crontab(minute=minute, hour=hour, day_of_month=dom, month_of_year=month, day_of_week=dow),
                    "options": {"queue": "periodic"},
                }

            logger.info(f"Loaded {len(schedule)} dynamic beat schedules from DB")
            return schedule

    except Exception as e:
        logger.warning(f"Failed to load dynamic schedule: {e}, using defaults")
        return {}


# ========== 静态 + 动态合并 ==========
# Celery Beat 启动时会读取此字典
DYNAMIC_SCHEDULE = load_dynamic_schedule()
