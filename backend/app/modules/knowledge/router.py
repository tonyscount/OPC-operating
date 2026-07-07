"""
知识库 API

POST   /knowledge/upload           — 上传文档
GET    /knowledge/documents        — 文档列表
GET    /knowledge/documents/{id}   — 文档详情
DELETE /knowledge/documents/{id}   — 删除文档
POST   /knowledge/documents/{id}/rechunk — 重新分块
GET    /knowledge/categories       — 分类列表
POST   /knowledge/categories       — 创建分类
DELETE /knowledge/categories/{id}  — 删除分类
GET    /knowledge/tags             — 标签列表
POST   /knowledge/tags             — 创建标签
POST   /knowledge/ask              — RAG 问答
GET    /knowledge/search           — 全文搜索
GET    /knowledge/stats            — 统计
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.core.database import get_db
from app.core.security import PermissionChecker, TokenPayload, get_current_user
from app.modules.knowledge import service as knowledge_svc
from app.modules.knowledge.models import KnowledgeDocument
from app.modules.knowledge.retrieval import RAGService, fulltext_search

router = APIRouter()
rag = RAGService()

require_kb_read = PermissionChecker("knowledge:read")
require_kb_upload = PermissionChecker("knowledge:upload")
require_kb_delete = PermissionChecker("knowledge:delete")


# ============================================================
# 文档
# ============================================================

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile, _: bool = Depends(require_kb_upload),
    title: str = Form(...),
    category_id: uuid.UUID | None = Form(None),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    上传文档并自动处理。

    流程: 保存临时文件 → 解析 → 分块 → 向量化 → 存储
    """
    import tempfile, os

    # 保存上传文件到临时目录
    suffix = os.path.splitext(file.filename or "unknown")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        doc = await knowledge_svc.upload_document(
            db,
            tenant_id=uuid.UUID(current_user.tenant_id),
            file_path=tmp_path,
            title=title,
            category_id=category_id,
        )
        return {
            "id": str(doc.id),
            "title": doc.title,
            "file_type": doc.file_type,
            "chunk_count": doc.chunk_count,
            "status": doc.status,
            "created_at": doc.created_at.isoformat(),
        }
    finally:
        os.unlink(tmp_path)  # 清理临时文件


@router.get("/documents")
async def list_documents(
    _: bool = Depends(require_kb_read),
    category_id: uuid.UUID | None = None,
    status: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """文档列表"""
    docs, total = await knowledge_svc.list_documents(
        db, uuid.UUID(current_user.tenant_id),
        category_id=category_id, status=status, keyword=keyword,
        page=page, page_size=page_size,
    )
    items = []
    for d in docs:
        tags = [{"id": str(t.id), "name": t.name} for t in (d.tags or [])]
        items.append({
            "id": str(d.id),
            "title": d.title,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "chunk_count": d.chunk_count,
            "status": d.status,
            "category_id": str(d.category_id) if d.category_id else None,
            "tags": tags,
            "created_at": d.created_at.isoformat(),
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/documents/expiring")
async def list_expiring_documents(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """列出即将过期和已过期的文档"""
    from sqlalchemy import select, or_
    docs = (await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.tenant_id == uuid.UUID(current_user.tenant_id),
            KnowledgeDocument.is_deleted == False,
            or_(KnowledgeDocument.freshness == "expiring_soon", KnowledgeDocument.freshness == "outdated"),
        ).order_by(KnowledgeDocument.freshness, KnowledgeDocument.expires_at)
    )).scalars().all()
    items = [{"id": str(d.id), "title": d.title, "freshness": d.freshness,
              "expires_at": d.expires_at, "chunk_count": d.chunk_count} for d in docs]
    return {"items": items, "total": len(items)}


@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: uuid.UUID,
    _: bool = Depends(require_kb_read),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """文档详情 (含分块内容)"""
    from sqlalchemy import select
    from app.modules.knowledge.models import DocumentChunk

    doc = await knowledge_svc.get_document(db, uuid.UUID(current_user.tenant_id), doc_id)
    chunks = (await db.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc_id).order_by(DocumentChunk.chunk_index)
    )).scalars().all()

    tags = [{"id": str(t.id), "name": t.name} for t in (doc.tags or [])]
    return {
        "id": str(doc.id),
        "title": doc.title,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "chunk_count": doc.chunk_count,
        "chunk_size": doc.chunk_size,
        "chunk_overlap": doc.chunk_overlap,
        "status": doc.status,
        "freshness": getattr(doc, 'freshness', 'valid'),
        "error_message": doc.error_message,
        "category_id": str(doc.category_id) if doc.category_id else None,
        "tags": tags,
        "content": "\n\n".join([c.content for c in chunks]),
        "chunks": [{"index": c.chunk_index, "content": c.content, "tokens": c.token_count} for c in chunks],
        "created_at": doc.created_at.isoformat(),
        "updated_at": doc.updated_at.isoformat(),
    }


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: uuid.UUID,
    _: bool = Depends(require_kb_delete),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """删除文档"""
    await knowledge_svc.delete_document(db, uuid.UUID(current_user.tenant_id), doc_id)


@router.post("/documents/{doc_id}/rechunk")
async def rechunk_document(
    doc_id: uuid.UUID,
    chunk_size: int = Form(512),
    chunk_overlap: int = Form(50),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """重新分块文档"""
    doc = await knowledge_svc.rechunk_document(
        db, uuid.UUID(current_user.tenant_id), doc_id,
        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
    )
    return {"id": str(doc.id), "status": doc.status, "chunk_size": doc.chunk_size}


# ============================================================
# 分类
# ============================================================

@router.post("/categories", status_code=status.HTTP_201_CREATED)
async def create_category(
    name: str = Form(...),
    description: str | None = Form(None),
    color: str | None = Form(None),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """创建分类"""
    cat = await knowledge_svc.create_category(
        db, uuid.UUID(current_user.tenant_id),
        name=name, description=description, color=color,
    )
    return {"id": str(cat.id), "name": cat.name, "description": cat.description, "color": cat.color}


@router.get("/categories")
async def list_categories(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """分类列表"""
    cats = await knowledge_svc.list_categories(db, uuid.UUID(current_user.tenant_id))
    return [
        {"id": str(c.id), "name": c.name, "description": c.description,
         "color": c.color, "sort_order": c.sort_order} for c in cats
    ]


@router.delete("/categories/{cat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    cat_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """删除分类"""
    await knowledge_svc.delete_category(db, uuid.UUID(current_user.tenant_id), cat_id)


# ============================================================
# 标签
# ============================================================

@router.post("/tags", status_code=status.HTTP_201_CREATED)
async def create_tag(
    name: str = Form(...),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """创建标签"""
    tag = await knowledge_svc.create_tag(db, uuid.UUID(current_user.tenant_id), name=name)
    return {"id": str(tag.id), "name": tag.name}


@router.get("/tags")
async def list_tags(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """标签列表"""
    tags = await knowledge_svc.list_tags(db, uuid.UUID(current_user.tenant_id))
    return [{"id": str(t.id), "name": t.name} for t in tags]


# ============================================================
# RAG 问答
# ============================================================

@router.post("/ask")
async def ask_question(
    _: bool = Depends(require_kb_read),
    question: str = Form(...),
    top_k: int = Form(5),
    category_id: uuid.UUID | None = Form(None),
    user_role: str | None = Form(None, description="新人/member/主理人 — 角色化分发"),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    RAG 问答: 基于知识库内容回答问题。
    user_role: 新人/核心成员/主理人 → 自动调整回答深度和风格
    """
    result = await rag.ask(
        db,
        tenant_id=uuid.UUID(current_user.tenant_id),
        question=question,
        user_role=user_role or "member",
        top_k=top_k,
        category_id=category_id,
    )
    return result


# ============================================================
# 全文搜索 (管理后台用)
# ============================================================

# ============================================================
# FAQ 批量导入 & 文本直接入库 (Layer 1.3)
# ============================================================

@router.post("/faq", status_code=status.HTTP_201_CREATED)
async def batch_import_faq(
    title: str = Form(..., description="FAQ 标题，如 'OPC新人百问百答'"),
    faqs: str = Form(..., description="Q&A 文本，每行格式: Q: 问题 / A: 答案"),
    category: str | None = Form(None),
    _: bool = Depends(require_kb_upload),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    批量导入 FAQ (Layer 1.3: 百问百答)。

    格式:
      Q: 如何加入OPC？
      A: 联系当地分社主理人，填写入社申请表。

      Q: 设备如何注册？
      A: 登录后在设备管理页面点击"注册设备"。
    """
    import tempfile, os

    content = f"# {title}\n\n> 类型: FAQ 百问百答\n> 分类: {category or '通用'}\n\n"
    for line in faqs.strip().split("\n"):
        line = line.strip()
        if line.startswith("Q:") or line.startswith("Q："):
            content += f"\n### {line}\n"
        elif line.startswith("A:") or line.startswith("A："):
            content += f"{line}\n"
        else:
            content += f"{line}\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(content)
        tmp_path = f.name

    try:
        doc = await knowledge_svc.upload_document(
            db, tenant_id=uuid.UUID(current_user.tenant_id),
            file_path=tmp_path, title=title,
        )
        return {"doc_id": str(doc.id), "title": doc.title, "status": doc.status, "chunks": doc.chunk_count}
    finally:
        os.unlink(tmp_path)


@router.post("/text", status_code=status.HTTP_201_CREATED)
async def upload_text(
    title: str = Form(...),
    content: str = Form(..., description="直接粘贴文本内容"),
    category: str | None = Form(None),
    _: bool = Depends(require_kb_upload),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    直接粘贴文本入库 (无需上传文件)。

    适用于: 活动复盘、会议记录、SOP 文档等场景。
    """
    import tempfile, os

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(content)
        tmp_path = f.name

    try:
        doc = await knowledge_svc.upload_document(
            db, tenant_id=uuid.UUID(current_user.tenant_id),
            file_path=tmp_path, title=title,
        )
        return {"doc_id": str(doc.id), "title": doc.title, "status": doc.status, "chunks": doc.chunk_count}
    finally:
        os.unlink(tmp_path)


@router.get("/search")
async def search_documents(
    q: str = Query(min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """全文搜索文档"""
    docs, total = await fulltext_search(
        db, uuid.UUID(current_user.tenant_id),
        query=q, page=page, page_size=page_size,
    )
    items = [{"id": str(d.id), "title": d.title, "file_type": d.file_type,
              "status": d.status} for d in docs]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ============================================================
# 知识保鲜 (Layer 2.2)
# ============================================================

@router.post("/documents/{doc_id}/renew")
async def renew_document(
    doc_id: uuid.UUID,
    new_expires_at: str | None = Form(None, description="新的过期日期 ISO format"),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """续期文档: 确认内容仍然有效，延长过期时间"""
    doc = await knowledge_svc.get_document(db, uuid.UUID(current_user.tenant_id), doc_id)
    from datetime import datetime, timedelta, timezone
    if new_expires_at:
        doc.expires_at = datetime.fromisoformat(new_expires_at)
    else:
        doc.expires_at = datetime.now(timezone.utc) + timedelta(days=90)
    doc.freshness = "valid"
    await db.commit()
    return {"id": str(doc.id), "expires_at": doc.expires_at, "freshness": doc.freshness}


""


# ============================================================
# 跨社群知识对比 (Layer 2.3: 匿名聚合，不暴露原始数据)
# ============================================================

@router.get("/cross-community")
async def cross_community_insight(
    topic: str | None = Query(None, description="关注话题，如 '设备注册' '新人培训'"),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    跨社群匿名对比: 查看其他组织的知识文档统计摘要。

    安全规则:
      - 只返回聚合统计，不暴露任何原始内容
      - 不显示具体是哪个城市/组织
      - 至少需要 3 个组织的数据才返回 (防单个推断)
    """
    from sqlalchemy import func, select

    conditions = [
        KnowledgeDocument.is_deleted == False,
        KnowledgeDocument.status == "ready",
        KnowledgeDocument.tenant_id != uuid.UUID(current_user.tenant_id),  # 排除自己的
    ]
    if topic:
        like = f"%{topic}%"
        conditions.append(KnowledgeDocument.title.ilike(like))

    total_docs = await db.scalar(
        select(func.count(KnowledgeDocument.id)).where(*conditions)
    )

    # 统计不同组织数量 (匿名)
    distinct_tenants = await db.scalar(
        select(func.count(func.distinct(KnowledgeDocument.tenant_id))).where(*conditions)
    )

    # 隐私保护: 少于 3 个组织不返回
    if distinct_tenants < 3:
        return {
            "available": False,
            "message": "数据不足，需要至少 3 个组织的数据才能提供对比 (保护隐私)",
            "tenants_count": distinct_tenants,
        }

    # 聚合统计
    from datetime import datetime, timedelta, timezone
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    recent = conditions + [KnowledgeDocument.created_at >= thirty_days_ago]
    recent_count = await db.scalar(
        select(func.count(KnowledgeDocument.id)).where(*recent)
    )

    return {
        "available": True,
        "topic": topic or "全部",
        "total_documents": total_docs,
        "organizations_count": distinct_tenants,
        "documents_last_30_days": recent_count or 0,
        "avg_docs_per_org": round(total_docs / distinct_tenants, 1) if distinct_tenants else 0,
        "privacy_note": "数据来自匿名聚合，不包含任何组织的具体信息",
    }


# ============================================================
# 统计
# ============================================================

@router.get("/stats")
async def get_stats(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """知识库统计信息"""
    return await knowledge_svc.get_stats(db, uuid.UUID(current_user.tenant_id))
