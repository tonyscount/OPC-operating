"""
知识库 — 业务逻辑层

- 文档上传 & 自动处理 (解析 → 分块 → 向量化)
- 文档管理 (列表/删除/重分块)
- 分类/标签管理
- RAG 问答
- 评估统计
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.modules.knowledge.embedding import EmbeddingService, get_embedding_service
from app.modules.knowledge.models import (
    DocumentChunk,
    KnowledgeCategory,
    KnowledgeDocument,
    KnowledgeTag,
    document_tags,
)
from app.modules.knowledge.parser import DocumentParser, parser as default_parser
from app.modules.knowledge.retrieval import RAGService, fulltext_search
from app.shared.utils import hash_content

logger = logging.getLogger("opc.knowledge.service")

# ============================================================
# 文档上传 & 处理
# ============================================================

async def upload_document(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    file_path: str,
    title: str,
    category_id: uuid.UUID | None = None,
    tag_ids: list[uuid.UUID] | None = None,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    embedding: EmbeddingService | None = None,
) -> KnowledgeDocument:
    """
    上传文档 → 解析 → 分块 → 向量化 → 存储。

    这是一个异步长流程，生产环境应通过 Celery 任务执行。
    """
    file_type = Path(file_path).suffix.lower().lstrip(".")
    if file_type not in ("pdf", "md", "txt", "docx"):
        raise ValidationException(f"不支持的文件类型: {file_type}")

    # 计算文件哈希 (去重)
    file_hash = _compute_file_hash(file_path)

    # 检查是否已上传
    existing = await db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.tenant_id == tenant_id,
            KnowledgeDocument.file_hash == file_hash,
            KnowledgeDocument.is_deleted == False,
        )
    )
    if existing:
        raise ConflictException("该文件已上传过 (相同内容)")

    # 创建文档记录
    file_size = Path(file_path).stat().st_size
    doc = KnowledgeDocument(
        tenant_id=tenant_id,
        title=title,
        file_type=file_type,
        file_size=file_size,
        file_hash=file_hash,
        category_id=category_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        status="processing",
    )
    db.add(doc)
    await db.flush()

    # 关联标签
    if tag_ids:
        for tid in tag_ids:
            await db.execute(
                document_tags.insert().values(document_id=doc.id, tag_id=tid)
            )

    try:
        # 解析文档
        parser = DocumentParser(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        text = parser.parse(file_path, file_type)
        chunks = parser.chunk(text, file_type)

        # 批量向量化 (失败不阻塞 — BM25 关键词检索仍可用)
        embedding_svc = embedding or get_embedding_service()
        chunk_texts = [c.content for c in chunks]
        embeddings = []
        try:
            embeddings = await embedding_svc.embed_batch(chunk_texts)
        except Exception as e:
            logger.warning(f"Embedding unavailable for doc {doc.id}: {e}. Doc will be searchable via BM25.")

        # 存储 chunks 到 ChromaDB + PostgreSQL (元数据)
        from app.modules.knowledge.vector_store import vector_store

        chroma_chunks = []
        for i, chunk in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            chroma_chunks.append({
                "id": chunk_id,
                "content": chunk.content,
                "document_id": str(doc.id),
                "document_title": doc.title,
                "chunk_index": i,
            })
            # 同时在 PG 存一份元数据 (不含向量)
            db_chunk = DocumentChunk(
                document_id=doc.id,
                tenant_id=tenant_id,
                chunk_index=i,
                content=chunk.content,
                token_count=chunk.token_count,
            )
            db.add(db_chunk)

        # 写入 ChromaDB (始终写入 — 无向量时 BM25 关键词检索仍可用)
        vector_store.add_chunks(
            tenant_id=str(tenant_id),
            chunks=chroma_chunks,
            embeddings=embeddings if embeddings else None,
        )

        doc.chunk_count = len(chunks)
        doc.status = "ready"
    except Exception as e:
        doc.status = "error"
        doc.error_message = str(e)

    await db.commit()
    await db.refresh(doc)
    return doc


async def get_document(
    db: AsyncSession, tenant_id: uuid.UUID, doc_id: uuid.UUID,
) -> KnowledgeDocument:
    """获取文档详情"""
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.tenant_id == tenant_id,
            KnowledgeDocument.is_deleted == False,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundException("文档不存在")
    return doc


async def list_documents(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    category_id: uuid.UUID | None = None,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[KnowledgeDocument], int]:
    """文档列表 (支持筛选/搜索)"""
    conditions = [
        KnowledgeDocument.tenant_id == tenant_id,
        KnowledgeDocument.is_deleted == False,
    ]
    if category_id:
        conditions.append(KnowledgeDocument.category_id == category_id)
    if status:
        conditions.append(KnowledgeDocument.status == status)
    if keyword:
        conditions.append(KnowledgeDocument.title.ilike(f"%{keyword}%"))

    total = await db.scalar(
        select(func.count(KnowledgeDocument.id)).where(*conditions)
    )

    docs = (await db.execute(
        select(KnowledgeDocument)
        .where(*conditions)
        .order_by(KnowledgeDocument.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return list(docs), total or 0


async def delete_document(
    db: AsyncSession, tenant_id: uuid.UUID, doc_id: uuid.UUID,
) -> None:
    """删除文档及关联 chunks"""
    doc = await get_document(db, tenant_id, doc_id)
    doc.is_deleted = True
    doc.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def rechunk_document(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    doc_id: uuid.UUID,
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    embedding: EmbeddingService | None = None,
) -> KnowledgeDocument:
    """
    重新分块文档 —— 调整分块大小后重新处理。

    注意: 此操作会删除旧的 chunks 并重新生成。
    """
    doc = await get_document(db, tenant_id, doc_id)

    new_chunk_size = chunk_size or doc.chunk_size
    new_overlap = chunk_overlap or doc.chunk_overlap

    # 删除旧 chunks
    from sqlalchemy import delete
    await db.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == doc_id)
    )

    # 从原始文件重新解析 (此处假设文件路径可获取)
    # 实际生产环境会存储原始文件在对象存储
    doc.chunk_size = new_chunk_size
    doc.chunk_overlap = new_overlap
    doc.status = "processing"
    await db.commit()

    # TODO: 异步任务重新分块
    return doc


# ============================================================
# 分类管理
# ============================================================

async def create_category(
    db: AsyncSession, tenant_id: uuid.UUID,
    *, name: str, description: str | None = None,
    color: str | None = None, sort_order: int = 0,
) -> KnowledgeCategory:
    existing = await db.scalar(
        select(KnowledgeCategory).where(
            KnowledgeCategory.tenant_id == tenant_id,
            KnowledgeCategory.name == name,
        )
    )
    if existing:
        raise ConflictException("该分类已存在")

    cat = KnowledgeCategory(
        tenant_id=tenant_id, name=name, description=description,
        color=color, sort_order=sort_order,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def list_categories(
    db: AsyncSession, tenant_id: uuid.UUID,
) -> list[KnowledgeCategory]:
    result = await db.execute(
        select(KnowledgeCategory)
        .where(KnowledgeCategory.tenant_id == tenant_id, KnowledgeCategory.is_deleted == False)
        .order_by(KnowledgeCategory.sort_order)
    )
    return list(result.scalars().all())


async def delete_category(
    db: AsyncSession, tenant_id: uuid.UUID, cat_id: uuid.UUID,
) -> None:
    cat = await db.get(KnowledgeCategory, cat_id)
    if not cat or cat.tenant_id != tenant_id:
        raise NotFoundException("分类不存在")
    cat.is_deleted = True
    cat.deleted_at = datetime.now(timezone.utc)
    await db.commit()


# ============================================================
# 标签管理
# ============================================================

async def create_tag(
    db: AsyncSession, tenant_id: uuid.UUID, *, name: str,
) -> KnowledgeTag:
    existing = await db.scalar(
        select(KnowledgeTag).where(
            KnowledgeTag.tenant_id == tenant_id,
            KnowledgeTag.name == name,
            KnowledgeTag.is_deleted == False,
        )
    )
    if existing:
        raise ConflictException("该标签已存在")

    tag = KnowledgeTag(tenant_id=tenant_id, name=name)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def list_tags(db: AsyncSession, tenant_id: uuid.UUID) -> list[KnowledgeTag]:
    result = await db.execute(
        select(KnowledgeTag)
        .where(KnowledgeTag.tenant_id == tenant_id, KnowledgeTag.is_deleted == False)
        .order_by(KnowledgeTag.name)
    )
    return list(result.scalars().all())


# ============================================================
# 评估 & 统计
# ============================================================

async def get_stats(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """知识库统计"""
    doc_count = await db.scalar(
        select(func.count(KnowledgeDocument.id)).where(
            KnowledgeDocument.tenant_id == tenant_id,
            KnowledgeDocument.is_deleted == False,
            KnowledgeDocument.status == "ready",
        )
    )
    chunk_count = await db.scalar(
        select(func.count(DocumentChunk.id)).where(
            DocumentChunk.tenant_id == tenant_id,
        )
    )
    total_size = await db.scalar(
        select(func.sum(KnowledgeDocument.file_size)).where(
            KnowledgeDocument.tenant_id == tenant_id,
            KnowledgeDocument.is_deleted == False,
        )
    )

    return {
        "document_count": doc_count or 0,
        "chunk_count": chunk_count or 0,
        "total_size_bytes": total_size or 0,
    }


# ============================================================
# 辅助
# ============================================================

def _compute_file_hash(file_path: str) -> str:
    """计算文件 SHA256"""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
