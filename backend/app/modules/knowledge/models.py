"""
知识库数据模型

- Document: 上传的文档元数据
- DocumentChunk: 分块后的文本 + pgvector 嵌入向量
- Category: 文档分类
- Tag: 文档标签
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.shared.models import TenantBase, UUIDMixin, TimestampMixin, Base

# ========== 多对多关联表 ==========
document_tags = Table(
    "document_tags",
    Base.metadata,
    sa.Column("document_id", UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("tag_id", UUID(as_uuid=True), ForeignKey("knowledge_tags.id", ondelete="CASCADE"), primary_key=True),
)


# ========== 文档 ==========
class KnowledgeDocument(TenantBase):
    __tablename__ = "knowledge_documents"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="pdf/md/txt/docx")
    file_size: Mapped[int] = mapped_column(Integer, default=0, comment="文件大小 (bytes)")
    file_hash: Mapped[str] = mapped_column(String(64), nullable=True, comment="SHA256 去重")
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_categories.id", ondelete="SET NULL")
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_size: Mapped[int] = mapped_column(Integer, default=512, comment="分块 token 数")
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[str] = mapped_column(
        String(20), default="processing", comment="processing/ready/error"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="过期时间。超过此时间文档标记为 outdated"
    )
    freshness: Mapped[str] = mapped_column(
        String(20), default="valid",
        comment="valid/expiring_soon/outdated — 保鲜状态"
    )

    # 关系
    category: Mapped["KnowledgeCategory | None"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    tags: Mapped[list["KnowledgeTag"]] = relationship(
        secondary=document_tags, back_populates="documents", lazy="selectin"
    )


# ========== 文档块 (向量) ==========
class DocumentChunk(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, comment="块序号 (从0开始)")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    # embedding 向量已迁移到 ChromaDB，此处仅存元数据
    chunk_meta: Mapped[dict] = mapped_column(
        "meta_json", String(2000), nullable=True, comment="JSON: page/section/source"
    )

    # 关系
    document: Mapped["KnowledgeDocument"] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_order"),
    )


# ========== 分类 ==========
class KnowledgeCategory(TenantBase):
    __tablename__ = "knowledge_categories"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True, comment="Hex 颜色")

    # 关系
    documents: Mapped[list["KnowledgeDocument"]] = relationship(back_populates="category")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_category_name_per_tenant"),
    )


# ========== 标签 ==========
class KnowledgeTag(TenantBase):
    __tablename__ = "knowledge_tags"

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # 关系
    documents: Mapped[list["KnowledgeDocument"]] = relationship(
        secondary=document_tags, back_populates="tags"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tag_name_per_tenant"),
    )
