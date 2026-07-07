"""
搜索 API

POST /api/v1/search          — 统一搜索
GET  /api/v1/search/stats    — 搜索统计
GET  /api/v1/search/suggest  — 搜索建议
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.config import settings
from app.core.database import get_db
from app.core.rate_limit import RATE_SOCIAL_SEARCH, limiter
from app.core.security import PermissionChecker, TokenPayload, get_current_user
from app.modules.search.schemas import SearchRequest, SearchResponse
from app.modules.search.service import MOCK_MODE, search

router = APIRouter()
require_search = PermissionChecker("search:read")


@router.post("", response_model=SearchResponse)
@limiter.limit(RATE_SOCIAL_SEARCH)
async def unified_search(
    req: SearchRequest, request: Request,
    _: bool = Depends(require_search),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    统一搜索入口。

    搜索范围 (自动根据 source_type 过滤):
      - knowledge: 知识库文档
      - social: 社交动态
      - user: 用户

    前端联调:
      - 开发环境且未配置 SEARCH_API_KEY → 自动使用 Mock 模式
      - 配置了 SEARCH_API_KEY → 调用真实搜索引擎
    """
    result = await search(
        db,
        tenant_id=uuid.UUID(current_user.tenant_id),
        query=req.query,
        page=req.page,
        page_size=req.page_size,
        filters=req.filters,
        sort=req.sort,
    )

    return SearchResponse(
        items=result["items"],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        has_more=result["has_more"],
        took_ms=result["took_ms"],
        query=result["query"],
        suggested_query=result.get("suggested_query"),
    )


@router.get("/suggest")
async def search_suggest(
    q: str = Query(min_length=1),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """搜索建议 (输入联想)"""
    # Mock: 简单返回空列表，生产环境接入搜索引擎的 suggest API
    return {"query": q, "suggestions": []}


@router.get("/status")
async def search_status():
    """查看当前搜索模式"""
    return {
        "mode": "mock" if MOCK_MODE else "external",
        "mock_mode": MOCK_MODE,
        "search_provider": settings.SEARCH_API_BASE_URL if not MOCK_MODE else "database",
    }


@router.post("/cache/clear")
async def clear_search_cache(
    current_user: TokenPayload = Depends(get_current_user),
):
    """清除搜索缓存"""
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL)
        count = 0
        async for key in r.scan_iter("search:*"):
            await r.delete(key)
            count += 1
        await r.close()
        return {"cleared": count}
    except Exception as e:
        return {"cleared": 0, "error": str(e)}
