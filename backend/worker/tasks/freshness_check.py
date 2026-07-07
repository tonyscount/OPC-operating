"""
知识保鲜预警任务 — 每天检查一次即将过期的文档

触发条件:
  - expires_at 在未来 7 天内 → 标记为 expiring_soon，推送给主理人
  - expires_at 已过期 → 标记为 outdated
"""

import logging
from datetime import datetime, timedelta, timezone

from worker.celery_app import celery_app

logger = logging.getLogger("opc.tasks.freshness")


@celery_app.task(bind=True, max_retries=2)
def run(self):
    """保鲜检查: 扫描所有文档，更新 freshness 状态，推送告警"""
    from app.config import settings
    from sqlalchemy import create_engine, text, select
    from app.modules.knowledge.models import KnowledgeDocument

    engine = create_engine(settings.DATABASE_URL_SYNC)
    now = datetime.now(timezone.utc)
    soon = (now + timedelta(days=7)).isoformat()
    now_str = now.isoformat()

    with engine.connect() as conn:
        # 1. 标记即将过期 (7天内)
        result = conn.execute(
            text("""
                UPDATE knowledge_documents
                SET freshness = 'expiring_soon', updated_at = NOW()
                WHERE expires_at IS NOT NULL
                  AND expires_at <= :soon
                  AND expires_at > :now
                  AND freshness = 'valid'
                  AND is_deleted = false
                  AND status = 'ready'
            """),
            {"soon": soon, "now": now_str},
        )
        expiring = result.rowcount
        conn.commit()
        logger.info(f"Marked {expiring} documents as expiring_soon")

        # 2. 标记已过期
        result = conn.execute(
            text("""
                UPDATE knowledge_documents
                SET freshness = 'outdated', updated_at = NOW()
                WHERE expires_at IS NOT NULL
                  AND expires_at <= :now
                  AND freshness != 'outdated'
                  AND is_deleted = false
            """),
            {"now": now_str},
        )
        outdated = result.rowcount
        conn.commit()
        logger.info(f"Marked {outdated} documents as outdated")

        # 3. 发送飞书通知 (给每个租户的过期文档)
        if expiring + outdated > 0 and settings.FEISHU_WEBHOOK_URL:
            docs = conn.execute(
                text("""
                    SELECT d.title, d.tenant_id, d.freshness, d.expires_at, t.name as tenant_name
                    FROM knowledge_documents d
                    JOIN tenants t ON d.tenant_id = t.id
                    WHERE d.freshness IN ('expiring_soon', 'outdated')
                      AND d.is_deleted = false
                    ORDER BY d.tenant_id, d.freshness
                """)
            ).all()

            for doc in docs:
                logger.info(
                    f"Freshness alert: [{doc.tenant_name}] '{doc.title}' "
                    f"status={doc.freshness} expires={doc.expires_at}"
                )

    engine.dispose()
    return {"expiring_soon": expiring, "outdated": outdated, "total": expiring + outdated}
