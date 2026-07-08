"""add_expires_at_and_freshness_to_knowledge_documents

Revision ID: 7336d36cf40b
Revises: 004
Create Date: 2026-07-08 20:00:07.560436
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7336d36cf40b'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 knowledge_documents.expires_at 和 freshness 列 (幂等)"""
    columns = _get_columns()
    if "expires_at" not in columns:
        op.add_column("knowledge_documents",
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True,
                      comment="过期时间。超过此时间文档标记为 outdated"))
    if "freshness" not in columns:
        op.add_column("knowledge_documents",
            sa.Column("freshness", sa.String(20), nullable=False,
                      server_default=sa.text("'valid'"),
                      comment="valid/expiring_soon/outdated — 保鲜状态"))


def downgrade() -> None:
    """移除 knowledge_documents.expires_at 和 freshness 列"""
    columns = _get_columns()
    if "freshness" in columns:
        op.drop_column("knowledge_documents", "freshness")
    if "expires_at" in columns:
        op.drop_column("knowledge_documents", "expires_at")


def _get_columns() -> set[str]:
    """获取 knowledge_documents 表当前所有列名"""
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'knowledge_documents'"
    ))
    return {row[0] for row in result}
