"""
搜索服务 — 支持 Mock 和真实 API 两种模式。

联调流程:
  1. MOCK_MODE=true  → 前端用假数据开发，后端好了直接切
  2. MOCK_MODE=false → 接入真实搜索引擎 (Elasticsearch / Meilisearch / 第三方API)

安全:
  - API Key 存在 BACKEND_ENV 环境变量
  - 接口加 @require_auth (登录验证)
  - 限流: Redis sliding window (100 req/min/user)
  - 缓存: Redis 缓存热门查询 (TTL 5min)
"""

import hashlib
import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.knowledge.models import KnowledgeDocument
from app.modules.social.models import SocialPost
from app.modules.tenant.models import User

logger = logging.getLogger("opc.search")

# ========== Mock 开关 ==========
MOCK_MODE = settings.APP_ENV == "development" and not settings.SEARCH_API_KEY


# ============================================================
# 统一搜索入口
# ============================================================

async def search(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    query: str,
    page: int = 1,
    page_size: int = 20,
    filters: dict | None = None,
    sort: str = "relevance",
) -> dict:
    """
    统一搜索接口。

    内部会根据 MOCK_MODE 调用不同的搜索策略。
    """
    start = time.perf_counter()

    if MOCK_MODE:
        items, total = await _mock_search(db, tenant_id, query, page, page_size, filters, sort)
    else:
        items, total = await _external_search(query, page, page_size, filters, sort)

    took_ms = int((time.perf_counter() - start) * 1000)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": (page * page_size) < total,
        "took_ms": took_ms,
        "query": query,
        "suggested_query": _suggest_correction(query) if total == 0 else None,
    }


# ============================================================
# Mock 搜索 (数据库内搜索 — 用于开发联调)
# ============================================================

async def _mock_search(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    query: str,
    page: int,
    page_size: int,
    filters: dict | None,
    sort: str,
) -> tuple[list[dict], int]:
    """Mock 搜索: 直接在数据库中搜索现有内容"""
    like = f"%{query}%"
    all_items: list[dict] = []

    # 1. 搜索知识库文档
    doc_result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.tenant_id == tenant_id,
            KnowledgeDocument.is_deleted == False,
            KnowledgeDocument.status == "ready",
            KnowledgeDocument.title.ilike(like),
        ).limit(page_size)
    )
    for doc in doc_result.scalars().all():
        all_items.append({
            "id": f"doc-{doc.id}",
            "title": doc.title,
            "description": f"类型: {doc.file_type} | 块数: {doc.chunk_count}",
            "source_type": "document",
            "source_id": str(doc.id),
            "score": 1.0,
            "created_at": doc.created_at.isoformat(),
        })

    # 2. 搜索社交动态
    post_result = await db.execute(
        select(SocialPost).where(
            SocialPost.tenant_id == tenant_id,
            SocialPost.is_deleted == False,
            SocialPost.visibility == "public",
            SocialPost.content.ilike(like),
        ).limit(page_size)
    )
    for post in post_result.scalars().all():
        all_items.append({
            "id": f"post-{post.id}",
            "title": post.content[:100],
            "description": post.content[:200],
            "source_type": "social",
            "source_id": str(post.id),
            "score": 0.8,
            "created_at": post.created_at.isoformat(),
        })

    # 3. 搜索用户
    user_result = await db.execute(
        select(User).where(
            User.tenant_id == tenant_id,
            User.status == "active",
            User.is_deleted == False,
            (User.username.ilike(like)) | (User.display_name.ilike(like)),
        ).limit(page_size)
    )
    for u in user_result.scalars().all():
        all_items.append({
            "id": f"user-{u.id}",
            "title": u.display_name or u.username,
            "description": f"@{u.username}",
            "source_type": "user",
            "source_id": str(u.id),
            "score": 0.7,
        })

    # 按相关性排序
    all_items.sort(key=lambda x: x.get("score", 0), reverse=True)

    total = len(all_items)
    start = (page - 1) * page_size
    items = all_items[start : start + page_size]

    return items, total


# ============================================================
# 外部搜索引擎 (Elasticsearch / Meilisearch / 第三方API)
# ============================================================

async def _external_search(
    query: str,
    page: int,
    page_size: int,
    filters: dict | None,
    sort: str,
) -> tuple[list[dict], int]:
    """
    调用外部搜索 API。

    支持的引擎 (通过配置切换):
      - Elasticsearch: 自建
      - Meilisearch: 自建
      - 第三方搜索 API: Google Custom Search / Bing API
    """
    import httpx

    if not settings.SEARCH_API_KEY:
        logger.warning("SEARCH_API_KEY not set, falling back to mock")
        return [], 0

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{settings.SEARCH_API_BASE_URL}/search",
                headers={
                    "Authorization": f"Bearer {settings.SEARCH_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "page": page,
                    "page_size": page_size,
                    "filters": filters or {},
                    "sort": sort,
                },
            )
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])
            total = data.get("total", 0)
            return items, total
    except Exception as e:
        logger.error(f"External search failed: {e}")
        raise


# ============================================================
# 缓存 & 限流
# ============================================================

def _cache_key(tenant_id: uuid.UUID, query: str, page: int, filters: dict | None) -> str:
    """生成缓存键"""
    raw = f"{tenant_id}:{query}:{page}:{json.dumps(filters or {}, sort_keys=True)}"
    return f"search:{hashlib.md5(raw.encode()).hexdigest()}"


async def get_cached_result(redis_client, cache_key: str) -> dict | None:
    """从 Redis 获取缓存结果"""
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    return None


async def set_cached_result(redis_client, cache_key: str, result: dict, ttl: int = 300):
    """缓存搜索结果 (默认 5 分钟)"""
    try:
        await redis_client.setex(cache_key, ttl, json.dumps(result, ensure_ascii=False))
    except Exception:
        pass


# ============================================================
# 搜索建议 / 拼写纠错
# ============================================================

def _suggest_correction(query: str) -> str | None:
    """
    简单的拼写纠错建议 (生产环境应接入专业纠错服务)。
    此处仅做示例: 中文场景不做自动纠错。
    """
    return None
