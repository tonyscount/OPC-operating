"""
搜索模块 — Pydantic Schemas

前后端联调约定的 JSON 结构。
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(min_length=1, max_length=500, description="搜索关键词")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)
    filters: dict[str, Any] | None = Field(
        default=None,
        description="筛选条件，如 { category: 'knowledge', date_from: '2026-01-01' }",
    )
    sort: str = Field(default="relevance", pattern="^(relevance|date|title)$")


class SearchResultItem(BaseModel):
    """单条搜索结果"""
    id: str
    title: str
    description: str | None = None  # 摘要/高亮片段
    source_type: str = Field(description="来源类型: knowledge/social/user/document")
    source_id: UUID | None = None
    url: str | None = None
    score: float | None = None
    highlights: dict[str, list[str]] | None = None  # 高亮字段
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None


class SearchResponse(BaseModel):
    """搜索响应 — 前后端约定格式"""
    items: list[SearchResultItem]
    total: int
    page: int
    page_size: int
    has_more: bool
    took_ms: int = 0  # 搜索耗时(毫秒)
    query: str
    suggested_query: str | None = None  # 拼写纠错建议


class SearchStats(BaseModel):
    """搜索统计 (管理后台用)"""
    total_searches: int
    avg_took_ms: float
    top_queries: list[dict[str, Any]]  # [{query, count}]
    zero_result_queries: list[dict[str, Any]]
