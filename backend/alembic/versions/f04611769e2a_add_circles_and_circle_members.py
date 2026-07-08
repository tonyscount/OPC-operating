"""add_circles_and_circle_members

Revision ID: f04611769e2a
Revises: 7336d36cf40b
Create Date: 2026-07-08 23:22:13.784799
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f04611769e2a'
down_revision: Union[str, None] = '7336d36cf40b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建圈子表 + 帖子加 circle_id"""
    from sqlalchemy.dialects import postgresql

    # 1. social_circles
    op.create_table(
        "social_circles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(30), nullable=False, server_default="general"),
        sa.Column("icon_url", sa.String(500), nullable=True),
        sa.Column("cover_url", sa.String(500), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("member_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("post_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_circles_tenant", "social_circles", ["tenant_id"])
    op.create_index("ix_circles_slug", "social_circles", ["tenant_id", "slug"], unique=True)

    # 2. social_circle_members
    op.create_table(
        "social_circle_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("circle_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("social_circles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_cm_circle", "social_circle_members", ["circle_id"])
    op.create_index("ix_cm_user", "social_circle_members", ["user_id"])

    # 3. social_posts 加 circle_id
    op.add_column("social_posts",
        sa.Column("circle_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("social_circles.id", ondelete="SET NULL"), nullable=True))


def downgrade() -> None:
    op.drop_column("social_posts", "circle_id")
    op.drop_table("social_circle_members")
    op.drop_table("social_circles")
