"""Phase 3-8 新增表 + RLS 全覆盖 + tenant_id 索引补充

Revision ID: 002
Revises: 001
Create Date: 2026-06-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 需要 RLS 的表清单 (所有含 tenant_id 的业务表)
RLS_TABLES = [
    "organizations", "roles", "social_likes", "user_follows", "user_friends",
    "login_logs", "schedule_tasks",
    "knowledge_documents", "knowledge_chunks", "knowledge_categories", "knowledge_tags",
    "agent_configs", "agent_executions",
    "trade_products", "trade_orders", "trade_order_items",
    "approval_templates", "approval_instances", "skills",
]

# 需要补充 tenant_id 索引的表
INDEX_TABLES = [
    "roles", "social_likes", "user_follows", "user_friends",
    "login_logs", "schedule_tasks",
]


def upgrade() -> None:
    # ============================================================
    # 知识库
    # ============================================================
    op.create_table(
        "knowledge_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("sort_order", sa.Integer, default=0),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "name", name="uq_category_name_per_tenant"),
    )

    op.create_table(
        "knowledge_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "name", name="uq_tag_name_per_tenant"),
    )

    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("file_size", sa.Integer, default=0),
        sa.Column("file_hash", sa.String(64), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("chunk_count", sa.Integer, default=0),
        sa.Column("chunk_size", sa.Integer, default=512),
        sa.Column("chunk_overlap", sa.Integer, default=50),
        sa.Column("status", sa.String(20), default="processing"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_docs_tenant", "knowledge_documents", ["tenant_id"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, default=0),
        sa.Column("embedding", postgresql.ARRAY(sa.Float), nullable=True),
        sa.Column("meta_json", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunk_order"),
    )
    op.create_index("ix_chunks_doc", "knowledge_chunks", ["document_id"])
    op.create_index("ix_chunks_tenant", "knowledge_chunks", ["tenant_id"])

    # document_tags 多对多关联表
    op.create_table(
        "document_tags",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_tags.id", ondelete="CASCADE"), primary_key=True),
    )

    # ============================================================
    # Agent
    # ============================================================
    op.create_table(
        "agent_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("role_prompt", sa.Text, nullable=False),
        sa.Column("tools", postgresql.JSONB, default=list),
        sa.Column("knowledge_base_ids", postgresql.JSONB, default=list),
        sa.Column("model", sa.String(100), default="gpt-4o"),
        sa.Column("temperature", sa.Float, default=0.3),
        sa.Column("max_iterations", sa.Integer, default=10),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("is_builtin", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "agent_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_configs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("thread_id", sa.String(100), nullable=False),
        sa.Column("orchestration_mode", sa.String(50), default="single"),
        sa.Column("status", sa.String(20), default="running"),
        sa.Column("input_message", sa.Text, nullable=False),
        sa.Column("output_message", sa.Text, nullable=True),
        sa.Column("state_snapshot", postgresql.JSONB, default=dict),
        sa.Column("checkpoint_id", sa.String(100), nullable=True),
        sa.Column("total_steps", sa.Integer, default=0),
        sa.Column("total_tokens", sa.Integer, default=0),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_exec_tenant", "agent_executions", ["tenant_id"])
    op.create_index("ix_agent_exec_thread", "agent_executions", ["thread_id"])

    op.create_table(
        "agent_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("agent_name", sa.String(200), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("tool_calls", postgresql.JSONB, nullable=True),
        sa.Column("tool_result", postgresql.JSONB, nullable=True),
        sa.Column("token_count", sa.Integer, default=0),
    )
    op.create_index("ix_agent_msg_exec", "agent_messages", ["execution_id"])

    # ============================================================
    # Skill
    # ============================================================
    op.create_table(
        "skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), unique=True, nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("parameters_schema", postgresql.JSONB, default=dict),
        sa.Column("handler_module", sa.String(500), nullable=True),
        sa.Column("handler_function", sa.String(200), nullable=True),
        sa.Column("timeout", sa.Integer, default=30),
        sa.Column("max_retries", sa.Integer, default=0),
        sa.Column("required_permissions", postgresql.JSONB, default=list),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("is_builtin", sa.Boolean, default=False),
        sa.Column("version", sa.String(20), default="1.0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ============================================================
    # OA 审批
    # ============================================================
    op.create_table(
        "approval_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("steps", postgresql.JSONB, default=list),
        sa.Column("form_schema", postgresql.JSONB, default=dict),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "approval_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("approval_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("applicant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("form_data", postgresql.JSONB, default=dict),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("current_step", sa.Integer, default=0),
        sa.Column("total_steps", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "approval_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("approval_instances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_order", sa.Integer, nullable=False),
        sa.Column("approver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approver_role", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ============================================================
    # 交易
    # ============================================================
    op.create_table(
        "trade_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("stock", sa.Integer, default=0),
        sa.Column("images", postgresql.JSONB, default=list),
        sa.Column("status", sa.String(20), default="published"),
        sa.Column("view_count", sa.Integer, default=0),
        sa.Column("order_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "trade_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("buyer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("paid_at", sa.String(50), nullable=True),
        sa.Column("remark", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "trade_order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trade_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trade_products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_title", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Integer, default=1),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ============================================================
    # RLS 全覆盖
    # ============================================================
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
                FOR ALL USING (tenant_filter(tenant_id))
                WITH CHECK (tenant_filter(tenant_id))
        """)

    # ============================================================
    # 补充 tenant_id 索引
    # ============================================================
    for table in INDEX_TABLES:
        op.create_index(f"ix_{table}_tenant", table, ["tenant_id"])


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")

    for table in INDEX_TABLES:
        op.drop_index(f"ix_{table}_tenant", table_name=table)

    op.drop_table("trade_order_items")
    op.drop_table("trade_orders")
    op.drop_table("trade_products")
    op.drop_table("approval_steps")
    op.drop_table("approval_instances")
    op.drop_table("approval_templates")
    op.drop_table("skills")
    op.drop_table("agent_messages")
    op.drop_table("agent_executions")
    op.drop_table("agent_configs")
    op.drop_table("document_tags")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("knowledge_tags")
    op.drop_table("knowledge_categories")
