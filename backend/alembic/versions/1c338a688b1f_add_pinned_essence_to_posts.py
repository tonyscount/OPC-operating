"""add_pinned_essence_to_posts

Revision ID: 1c338a688b1f
Revises: bccf30bb328d
Create Date: 2026-07-09 15:51:25.680457
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c338a688b1f'
down_revision: Union[str, None] = 'bccf30bb328d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("social_posts", sa.Column("is_pinned", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("social_posts", sa.Column("is_essence", sa.Boolean, nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("social_posts", "is_essence")
    op.drop_column("social_posts", "is_pinned")
