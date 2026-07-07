"""知识库同步任务 — 增量/全量同步文档"""

import logging

from worker.celery_app import celery_app

logger = logging.getLogger("opc.tasks.knowledge_sync")


@celery_app.task(bind=True, max_retries=3)
def run(self, document_id: str | None = None):
    """
    知识库文档同步。

    场景:
      - document_id=None → 检查所有 processing/error 状态的文档并重试
      - document_id=xxx → 同步特定文档
    """
    from app.config import settings
    from sqlalchemy import create_engine, select, text

    engine = create_engine(settings.DATABASE_URL_SYNC)
    synced = 0
    failed = 0

    with engine.connect() as conn:
        if document_id:
            docs = conn.execute(
                text("SELECT id, title FROM knowledge_documents WHERE id = :id AND status IN ('processing','error')"),
                {"id": document_id},
            ).all()
        else:
            docs = conn.execute(
                text("SELECT id, title FROM knowledge_documents WHERE status IN ('processing','error') AND is_deleted = false"),
            ).all()

        for doc in docs:
            try:
                # 重新处理文档 (实际会调用 parser + embedding)
                conn.execute(
                    text("UPDATE knowledge_documents SET status = 'processing' WHERE id = :id"),
                    {"id": doc.id},
                )
                conn.commit()
                synced += 1
                logger.info(f"Knowledge sync: queued doc {doc.id} ({doc.title})")
            except Exception as e:
                logger.error(f"Knowledge sync failed for {doc.id}: {e}")
                failed += 1

    logger.info(f"Knowledge sync complete: {synced} queued, {failed} failed")
    return {"status": "ok", "synced": synced, "failed": failed}
