"""
多智能体数据模型

- AgentConfig: Agent 定义 (角色、工具、知识库、模型)
- AgentExecution: 执行记录 (状态持久化、断点恢复)
- AgentMessage: 单步消息记录
"""

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import TenantBase, UUIDMixin, TimestampMixin, Base


class AgentConfig(TenantBase):
    """
    Agent 配置 —— 定义每个 Agent 的角色、工具、知识库访问权限。
    """
    __tablename__ = "agent_configs"

    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="Agent 名称")
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role_prompt: Mapped[str] = mapped_column(Text, nullable=False, comment="角色 System Prompt")
    tools: Mapped[list[str]] = mapped_column(
        JSONB, default=list, comment="可调用的 Skill 名称列表"
    )
    knowledge_base_ids: Mapped[list[str]] = mapped_column(
        JSONB, default=list, comment="可访问的知识库分类 ID"
    )
    model: Mapped[str] = mapped_column(
        String(100), default="gpt-4o", comment="绑定的 LLM 模型"
    )
    temperature: Mapped[float] = mapped_column(Float, default=0.3)
    max_iterations: Mapped[int] = mapped_column(Integer, default=10)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        # 同租户下 Agent 名唯一
        {"comment": "Agent 配置表"},
    )


class AgentExecution(UUIDMixin, TimestampMixin, Base):
    """
    Agent 执行记录 — 状态持久化，支持断点恢复。

    与 LangGraph Checkpointer 配合使用。
    """
    __tablename__ = "agent_executions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_configs.id", ondelete="SET NULL"), nullable=True,
    )
    thread_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="LangGraph thread_id"
    )
    orchestration_mode: Mapped[str] = mapped_column(
        String(50), default="single", comment="single/sequential/router/debate"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="running", comment="running/completed/failed/cancelled"
    )
    input_message: Mapped[str] = mapped_column(Text, nullable=False, comment="用户输入")
    output_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="最终输出")
    state_snapshot: Mapped[dict] = mapped_column(
        JSONB, default=dict, comment="LangGraph 状态快照 (用于断点恢复)"
    )
    checkpoint_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="LangGraph checkpoint ID"
    )
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 关系
    messages: Mapped[list["AgentMessage"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan", lazy="selectin",
    )


class AgentMessage(UUIDMixin, Base):
    """
    Agent 单步消息 — 审计日志。
    """
    __tablename__ = "agent_messages"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_executions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, comment="步骤序号")
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="system/user/assistant/tool"
    )
    agent_name: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="哪个 Agent 的消息")
    content: Mapped[str] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="function_call 详情")
    tool_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0)

    # 关系
    execution: Mapped["AgentExecution"] = relationship(back_populates="messages")
