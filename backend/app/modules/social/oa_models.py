"""
OA 审批工作流模型

- ApprovalTemplate: 审批模板 (请假/报销/采购...)
- ApprovalInstance: 审批实例 (一次具体申请)
- ApprovalStep: 审批步骤记录
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import TenantBase, UUIDMixin, TimestampMixin, Base


class ApprovalTemplate(TenantBase):
    """审批模板"""
    __tablename__ = "approval_templates"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="leave/reimbursement/purchase/custom"
    )
    steps: Mapped[list[dict]] = mapped_column(
        JSONB, default=list,
        comment='审批步骤定义: [{"order":1,"approver_role":"manager","name":"直属上级审批"}]'
    )
    form_schema: Mapped[dict] = mapped_column(
        JSONB, default=dict, comment='前端表单 JSON Schema'
    )
    enabled: Mapped[bool] = mapped_column(default=True)


class ApprovalInstance(TenantBase):
    """审批实例"""
    __tablename__ = "approval_instances"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_templates.id", ondelete="SET NULL"), nullable=True,
    )
    applicant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    form_data: Mapped[dict] = mapped_column(JSONB, default=dict, comment="表单填写数据")
    status: Mapped[str] = mapped_column(
        String(20), default="pending", comment="pending/approved/rejected/cancelled"
    )
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)

    steps: Mapped[list["ApprovalStep"]] = relationship(
        back_populates="instance", cascade="all, delete-orphan", lazy="selectin",
    )


class ApprovalStep(UUIDMixin, TimestampMixin, Base):
    """审批步骤"""
    __tablename__ = "approval_steps"

    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_instances.id", ondelete="CASCADE"), nullable=False,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    approver_role: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        String(20), default="pending", comment="pending/approved/rejected/skipped"
    )
    comment: Mapped[str | None] = mapped_column(Text)

    instance: Mapped["ApprovalInstance"] = relationship(back_populates="steps")
