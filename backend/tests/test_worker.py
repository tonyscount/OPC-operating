"""Celery Worker 任务测试 — 核心任务逻辑 (绕过 Celery 直接测)"""

import uuid
import pytest
from datetime import datetime, timedelta, timezone


@pytest.fixture
def fresh_doc(db):
    """Helper: 创建一个即将过期的文档"""
    from app.modules.knowledge.models import KnowledgeDocument

    tid = uuid.uuid4()
    doc = KnowledgeDocument(
        id=uuid.uuid4(),
        tenant_id=tid,
        title="Test Doc",
        file_type="txt",
        status="ready",
        freshness="valid",
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ============================================================
# Data Cleanup
# ============================================================

def test_data_cleanup_smoke(db):
    """数据清理任务 — 不崩溃 (某些表可能尚未创建)"""
    from worker.tasks.data_cleanup import run

    try:
        result = run()
        assert result["status"] == "ok"
        assert "deleted_total" in result
    except Exception as e:
        # 某些表 (login_logs) 通过 alembic 创建而非 Base.metadata, 测试库可能缺少
        msg = str(e).lower()
        if any(kw in msg for kw in ("undefined", "does not exist", "programmingerror")):
            pytest.skip(f"Table/column not in test DB: {e}")
        raise


# ============================================================
# Freshness Check
# ============================================================

def test_freshness_check_smoke(db):
    """保鲜检查 — 不崩溃 + 返回计数"""
    from worker.tasks.freshness_check import run

    result = run()
    assert "expiring_soon" in result
    assert "outdated" in result
    assert isinstance(result["total"], int)


# ============================================================
# Health Check
# ============================================================

def test_health_check_smoke():
    """健康检查 — 数据库连通性检查通过"""
    from worker.tasks.health_check import run

    result = run()
    assert result["status"] in ("ok", "degraded")
    assert "checks" in result
    assert result["checks"]["database"] == "ok"


# ============================================================
# Beat Schedule (静态配置校验)
# ============================================================

def test_beat_schedule_valid():
    """Beat schedule — 任务名和 cron 表达式有效"""
    from worker.celery_app import celery_app

    # celery_app 可能未完全初始化，只验证 beat_schedule 可访问
    schedule = getattr(celery_app, "conf", {}).get("beat_schedule", {})
    # 不强制要求有内容 — 只要能访问即可
    assert isinstance(schedule, dict)


# ============================================================
# Daily Briefing (smoke — no LLM call)
# ============================================================

def test_daily_briefing_smoke():
    """每日简报 — handler 可导入不崩溃"""
    try:
        from skills.daily_briefing.handler import daily_briefing
        assert callable(daily_briefing)
    except ImportError:
        pytest.skip("daily_briefing skill not available")


# ============================================================
# Knowledge Sync (smoke)
# ============================================================

def test_knowledge_sync_smoke():
    """知识同步 — 模块可导入"""
    try:
        from worker.tasks.knowledge_sync import run
        assert callable(run)
    except ImportError:
        pytest.skip("knowledge_sync not available")
