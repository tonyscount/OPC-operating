"""Skill 系统 Schemas"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SkillParamSchema(BaseModel):
    """参数定义"""
    type: str = "string"
    description: str = ""
    required: bool = True
    default: Any = None
    enum: list[Any] | None = None


class SkillCreate(BaseModel):
    """创建 Skill"""
    name: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, description="给 Agent 看的功能描述")
    parameters_schema: dict = Field(default_factory=dict)
    timeout: int = Field(default=30, ge=1, le=600)
    max_retries: int = Field(default=0, ge=0, le=5)
    required_permissions: list[str] = Field(default_factory=list)


class SkillUpdate(BaseModel):
    """更新 Skill"""
    display_name: str | None = None
    description: str | None = None
    parameters_schema: dict | None = None
    timeout: int | None = None
    max_retries: int | None = None
    required_permissions: list[str] | None = None
    enabled: bool | None = None


class SkillResponse(BaseModel):
    id: UUID
    name: str
    display_name: str
    description: str
    parameters_schema: dict
    timeout: int
    max_retries: int
    required_permissions: list[str]
    enabled: bool
    is_builtin: bool
    version: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SkillExecutionRequest(BaseModel):
    """Skill 执行请求"""
    skill_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None  # 用于链路追踪


class SkillExecutionResponse(BaseModel):
    """Skill 执行结果"""
    success: bool
    skill_name: str
    result: Any = None
    error: str | None = None
    took_ms: int = 0
    trace_id: str | None = None
