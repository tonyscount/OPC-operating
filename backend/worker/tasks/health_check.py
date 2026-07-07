"""健康检查任务 — 定期检查各组件连通性"""

import logging

from worker.celery_app import celery_app

logger = logging.getLogger("opc.tasks.health_check")


@celery_app.task(bind=True, max_retries=1)
def run(self):
    """定期检查数据库、Redis、磁盘空间，异常时发飞书告警"""
    from app.config import settings
    import os
    import shutil

    checks = {}

    # 1. 数据库检查
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(settings.DATABASE_URL_SYNC)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        logger.error(f"Health check: database DOWN: {e}")

    # 2. Redis 检查
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        logger.error(f"Health check: redis DOWN: {e}")

    # 3. 磁盘空间检查
    try:
        usage = shutil.disk_usage(settings.BASE_DIR)
        free_gb = usage.free / (1024 ** 3)
        checks["disk"] = "ok" if free_gb > 1 else f"low: {free_gb:.1f}GB"
        if free_gb < 1:
            logger.warning(f"Health check: low disk space ({free_gb:.1f}GB)")
    except Exception as e:
        checks["disk"] = f"error: {e}"

    # 4. 飞书告警 (如有异常)
    all_ok = all(v == "ok" for v in checks.values())
    if not all_ok and settings.FEISHU_WEBHOOK_URL:
        import json, urllib.request
        payload = json.dumps({
            "msg_type": "text",
            "content": {"text": f"🚨 OPC 健康检查异常\n" + "\n".join(f"- {k}: {v}" for k, v in checks.items())},
        }).encode()
        try:
            req = urllib.request.Request(settings.FEISHU_WEBHOOK_URL, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    return {"status": "ok" if all_ok else "degraded", "checks": checks}
