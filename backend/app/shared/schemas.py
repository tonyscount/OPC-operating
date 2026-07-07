"""公共 Pydantic Schema 定义"""

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ========== 泛型分页 ==========
T = TypeVar("T")


class PaginationParams(BaseModel):
    """分页请求参数"""
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: list[T]
    total: int
    page: int
    page_size: int
    has_more: bool


# ========== 通用响应 ==========
class APIResponse(BaseModel, Generic[T]):
    """标准 API 响应信封"""
    success: bool = True
    data: T | None = None
    message: str = "OK"
    request_id: str | None = None


# ========== 时间戳 Schema ==========
class TimestampSchema(BaseModel):
    created_at: datetime
    updated_at: datetime


class BaseSchema(TimestampSchema):
    """基础输出 Schema"""
    model_config = ConfigDict(from_attributes=True)
    id: UUID
