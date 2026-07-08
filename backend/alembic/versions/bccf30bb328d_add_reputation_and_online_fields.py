"""add_reputation_and_online_fields

Revision ID: bccf30bb328d
Revises: f04611769e2a
Create Date: 2026-07-08 23:39:00.173204
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bccf30bb328d'
down_revision: Union[str, None] = 'f04611769e2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """用户表加信誉分、等级、最后在线时间"""
    op.add_column("users", sa.Column("reputation_score", sa.Integer, nullable=False, server_default="0"))
    op.add_column("users", sa.Column("level", sa.String(20), nullable=False, server_default="bronze"))
    op.add_column("users", sa.Column("last_online_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_online_at")
    op.drop_column("users", "level")
    op.drop_column("users", "reputation_score")
