"""补全 RLS + DateTime 类型修复

Revision ID: 004
Revises: 003
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels = None
depends_on = None

# 缺 RLS 的表
MISSING_RLS_TABLES = [
    "notifications",
    "conversations",
    "conversation_participants",
    "messages",
]

# String → DateTime 列迁移
STRING_DATE_COLS = [
    ("conversations",      "last_message_at"),
    ("messages",           "read_at"),
    ("notifications",      "read_at"),
    ("devices",            "last_online_at"),
    ("user_statuses",      "expires_at"),
    ("knowledge_documents","expires_at"),
    ("trade_orders",       "paid_at"),
]


def upgrade():
    # ---- 1. conversation_participants 补 tenant_id ----
    # 检查列是否已存在 (幂等)
    result = op.get_bind().execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
        "WHERE table_name='conversation_participants' AND column_name='tenant_id')"
    ))
    if not result.scalar():
        op.add_column("conversation_participants",
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True))
        # 从关联的 conversations 回填 tenant_id
        op.execute("""
            UPDATE conversation_participants cp
            SET tenant_id = c.tenant_id
            FROM conversations c
            WHERE cp.conversation_id = c.id
        """)
        op.alter_column("conversation_participants", "tenant_id", nullable=False)

    # conversation_participants 补软删除字段 (幂等)
    result = op.get_bind().execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
        "WHERE table_name='conversation_participants' AND column_name='is_deleted')"
    ))
    if not result.scalar():
        op.add_column("conversation_participants",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    result = op.get_bind().execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
        "WHERE table_name='conversation_participants' AND column_name='deleted_at')"
    ))
    if not result.scalar():
        op.add_column("conversation_participants",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    # ---- 2. String → DateTime 类型迁移 ----
    for table, col in STRING_DATE_COLS:
        # 先检查列类型，只对 varchar/text 列做转换 (幂等)
        col_info = op.get_bind().execute(sa.text(
            f"SELECT data_type FROM information_schema.columns "
            f"WHERE table_name='{table}' AND column_name='{col}'"
        ))
        row = col_info.fetchone()
        if row and row[0] in ('character varying', 'text', 'varchar'):
            op.execute(f"""
                ALTER TABLE {table}
                ALTER COLUMN {col} TYPE TIMESTAMP WITH TIME ZONE
                USING {col}::timestamp with time zone
            """)

    # ---- 3. 所有缺失表启用 RLS (幂等) ----
    for t in MISSING_RLS_TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"DO $$ BEGIN "
            f"  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='tenant_isolation_{t}') THEN "
            f"    CREATE POLICY tenant_isolation_{t} ON {t} "
            f"    FOR ALL USING (tenant_filter(tenant_id)) "
            f"    WITH CHECK (tenant_filter(tenant_id)); "
            f"  END IF; "
            f"END $$"
        )

    # ---- 4. conversation_participants 补索引 (幂等，002 已建则跳过) ----
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_cp_conversation_id ON conversation_participants (conversation_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_cp_tenant_id ON conversation_participants (tenant_id)
    """)


def downgrade():
    # 移除 RLS
    for t in MISSING_RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{t} ON {t}")

    # 移除 cp 索引 (幂等)
    op.execute("DROP INDEX IF EXISTS ix_cp_tenant_id")
    op.execute("DROP INDEX IF EXISTS ix_cp_conversation_id")

    # 移除 cp 软删除字段
    op.drop_column("conversation_participants", "deleted_at")
    op.drop_column("conversation_participants", "is_deleted")

    # 移除 cp tenant_id
    op.drop_column("conversation_participants", "tenant_id")

    # DateTime → String 回退 (不保留数据)
    for table, col in STRING_DATE_COLS:
        op.execute(f"""
            ALTER TABLE {table}
            ALTER COLUMN {col} TYPE VARCHAR(50)
            USING {col}::text
        """)
