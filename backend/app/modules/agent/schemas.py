"""Agent 模块 Schemas"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    role_prompt: str = Field(min_length=1, description="角色 System Prompt")
    tools: list[str] = Field(default_factory=list, description="可调用的 Skill 名称")
    knowledge_base_ids: list[str] = Field(default_factory=list)
    model: str = Field(default="gpt-4o")
    temperature: float = Field(default=0.3, ge=0, le=2)
    max_iterations: int = Field(default=10, ge=1, le=100)


class AgentUpdate(BaseModel):
    display_name: str | None = None
    role_prompt: str | None = None
    tools: list[str] | None = None
    knowledge_base_ids: list[str] | None = None
    model: str | None = None
    temperature: float | None = None
    max_iterations: int | None = None
    enabled: bool | None = None


class AgentResponse(BaseModel):
    id: UUID
    name: str
    display_name: str
    role_prompt: str
    tools: list[str]
    knowledge_base_ids: list[str]
    model: str
    temperature: float
    max_iterations: int
    enabled: bool
    is_builtin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentExecutionRequest(BaseModel):
    """Agent 执行请求"""
    agent_name: str | None = None  # 单个 Agent
    mode: str = Field(default="single", pattern="^(single|sequential|router|debate)$")
    message: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    stream: bool = False


class AgentExecutionResponse(BaseModel):
    execution_id: UUID
    thread_id: str
    status: str
    output: str | None = None
    total_steps: int = 0
    messages: list[dict] = []
    error: str | None = None
