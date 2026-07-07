"""
Celery 应用配置 & Beat 定时调度
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

# ========== Celery 实例 ==========
celery_app = Celery(
    "opc_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,  # 结果也存 Redis
    include=[
        "worker.tasks.knowledge_sync",
        "worker.tasks.data_cleanup",
        "worker.tasks.report_gen",
        "worker.tasks.health_check",
        "worker.tasks.freshness_check",
        "worker.tasks.daily_briefing",
        "worker.tasks.sync_counters",
        "worker.tasks.db_backup",
    ],
)

# ========== 通用配置 ==========
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_acks_late=True,  # 任务完成后才确认 (防丢失)
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_time_limit=600,  # 单任务最大 10 分钟
    task_soft_time_limit=540,  # 软超时 9 分钟
    task_default_retry_delay=60,
    task_max_retries=3,
    worker_prefetch_multiplier=1,  # 每次只取 1 个任务 (避免长任务阻塞)
    result_expires=3600,  # 结果 1 小时后过期
)

# ========== Beat 定时调度 ==========
celery_app.conf.beat_schedule = {
    # 示例: 每小时做一次健康检查
    "health-check-every-hour": {
        "task": "worker.tasks.health_check.run",
        "schedule": crontab(minute="0", hour="*"),
        "options": {"queue": "periodic"},
    },
    # 示例: 每天凌晨 2 点清理过期数据
    "data-cleanup-daily": {
        "task": "worker.tasks.data_cleanup.run",
        "schedule": crontab(minute="0", hour="2"),
        "options": {"queue": "periodic"},
    },
    # 示例: 每天凌晨 3 点生成日报
    "report-gen-daily": {
        "task": "worker.tasks.report_gen.run_daily",
        "schedule": crontab(minute="0", hour="3"),
        "options": {"queue": "periodic"},
    },
    # 知识库同步 — 每 30 分钟
    "knowledge-sync": {
        "task": "worker.tasks.knowledge_sync.run",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "periodic"},
    },
    # 知识保鲜预警 — 每天 8:00
    "freshness-check-daily": {
        "task": "worker.tasks.freshness_check.run",
        "schedule": crontab(minute="0", hour="8"),
        "options": {"queue": "periodic"},
    },
    # 每日运营简报 — 每天 8:10 (保鲜之后)
    "daily-briefing": {
        "task": "worker.tasks.daily_briefing.run",
        "schedule": crontab(minute="10", hour="8"),
        "options": {"queue": "periodic"},
    },
    # Redis 计数器 → DB 同步 — 每 30 秒
    "sync-counters": {
        "task": "sync_counters_to_db",
        "schedule": 30.0,
        "options": {"queue": "periodic"},
    },
    # 数据库备份 — 每天凌晨 3:00
    "db-backup-daily": {
        "task": "db_backup_daily",
        "schedule": crontab(minute="0", hour="3"),
        "options": {"queue": "periodic"},
    },
}
