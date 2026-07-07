"""定时任务模型"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, UUIDMixin, TimestampMixin


class ScheduleTask(UUIDMixin, TimestampMixin, Base):
    """定时任务注册表"""
    __tablename__ = "schedule_tasks"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="任务名称")
    task_key: Mapped[str] = mapped_column(
        String(200), unique=True, nullable=False, comment="Celery task name"
    )
    cron_expression: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Cron 表达式: 分 时 日 月 周"
    )
    description: Mapped[str] = mapped_column(Text, nullable=True)
    params: Mapped[dict] = mapped_column(JSONB, default=dict, comment="任务参数")
    enabled: Mapped[bool] = mapped_column(default=True, comment="是否启用")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskExecution(UUIDMixin, Base):
    """任务执行记录"""
    __tablename__ = "task_executions"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schedule_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="running", comment="running/success/failed/timeout"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(default=0)
