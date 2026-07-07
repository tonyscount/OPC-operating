"""设备 + 发现页 表

Revision ID: 003
Revises: 002
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels = None
depends_on = None

NEW_RLS_TABLES = ["devices", "user_statuses", "user_skills", "greets"]


def upgrade():
    # 设备
    op.create_table("devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", postgresql.UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("device_type", sa.String(50), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("port", sa.Integer, nullable=True),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("status", sa.String(20), default="offline"),
        sa.Column("last_online_at", sa.String(50), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("specs", postgresql.JSONB, default=dict),
        sa.Column("tags", postgresql.JSONB, default=list),
        sa.Column("view_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, default=False), sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_devices_tenant", "devices", ["tenant_id"])
    op.create_index("ix_devices_owner", "devices", ["owner_id"])

    # 用户状态
    op.create_table("user_statuses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("tenant_id", postgresql.UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("emoji", sa.String(10), nullable=True),
        sa.Column("text", sa.String(100), nullable=False),
        sa.Column("background_url", sa.String(500), nullable=True),
        sa.Column("expires_at", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 技能标签
    op.create_table("user_skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("level", sa.String(20), default="intermediate"),
        sa.Column("endorsed_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, default=False), sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 打招呼
    op.create_table("greets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("from_user_id", postgresql.UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_user_id", postgresql.UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("latitude", sa.Float, nullable=True), sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    for t in NEW_RLS_TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation_{t} ON {t} FOR ALL USING (tenant_filter(tenant_id)) WITH CHECK (tenant_filter(tenant_id))")


def downgrade():
    for t in NEW_RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{t} ON {t}")
    op.drop_table("greets")
    op.drop_table("user_skills")
    op.drop_table("user_statuses")
    op.drop_table("devices")
