"""
每日简报 Celery 任务 — 每天 8:00 自动执行
"""

import logging
from worker.celery_app import celery_app

logger = logging.getLogger("opc.tasks.daily_briefing")


@celery_app.task(bind=True, max_retries=2)
def run(self):
    """为所有活跃租户生成每日简报"""
    from app.config import settings
    from sqlalchemy import create_engine, text

    engine = create_engine(settings.DATABASE_URL_SYNC)
    results = []

    with engine.connect() as conn:
        tenants = conn.execute(
            text("SELECT id, name FROM tenants WHERE status = 'active'")
        ).all()

        for tenant in tenants:
            tid = str(tenant.id)
            tname = tenant.name
            try:
                import asyncio
                from skills.daily_briefing.handler import daily_briefing

                briefing = asyncio.run(daily_briefing(tenant_id=tid))
                results.append({
                    "tenant": tname,
                    "snapshot": briefing.get("data_snapshot"),
                    "generated": briefing.get("generated_at"),
                })
                logger.info(f"Briefing generated for {tname}: members={briefing.get('data_snapshot', {}).get('members')}")

                # 如果有飞书 Webhook，发送简报
                if settings.FEISHU_WEBHOOK_URL:
                    text = briefing.get("briefing", "")
                    _send_feishu(settings.FEISHU_WEBHOOK_URL, f"📊 {tname} 每日运营简报\n\n{text}")

            except Exception as e:
                logger.error(f"Briefing failed for {tname}: {e}")
                results.append({"tenant": tname, "error": str(e)})

    engine.dispose()
    return {"briefings": len(results), "results": results}


def _send_feishu(webhook: str, text: str):
    """发送飞书消息"""
    try:
        import json, urllib.request
        payload = json.dumps({"msg_type": "text", "content": {"text": text[:4000]}}).encode()
        req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass
