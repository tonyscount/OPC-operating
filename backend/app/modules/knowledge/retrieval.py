"""
RAG 检索 & 问答服务 (ChromaDB 版本)

流程:
  1. 用户提问 → 向量化
  2. ChromaDB 相似度搜索 TOP-N 文本块
  3. 拼接 Prompt → 调用 LLM 生成回答
  4. 返回答案 + 引用来源
"""

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.knowledge.embedding import EmbeddingService, get_embedding_service
from app.modules.knowledge.vector_store import vector_store

logger = logging.getLogger("opc.retrieval")


class RAGService:
    """RAG 检索增强生成服务 (ChromaDB)"""

    def __init__(self, embedding: EmbeddingService | None = None):
        self.embedding = embedding or get_embedding_service()
        self._llm_client = None

    @property
    def llm_client(self):
        if self._llm_client is None:
            from openai import AsyncOpenAI
            self._llm_client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )
        return self._llm_client

    async def search(
        self,
        tenant_id: uuid.UUID,
        query: str,
        top_k: int = 5,
        document_id: uuid.UUID | None = None,
        min_score: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        向量相似度搜索 (ChromaDB)。
        """
        if not self.embedding.is_available:
            logger.warning("RAG search: embedding service not available")
            return []

        query_embedding = await self.embedding.embed_query(query)
        if not query_embedding:
            return []

        where = None
        if document_id:
            where = {"document_id": str(document_id)}

        results = vector_store.search(
            tenant_id=str(tenant_id),
            query_embedding=query_embedding,
            top_k=top_k,
            where=where,
        )

        return [r for r in results if r["score"] >= min_score]

    async def ask(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        question: str,
        top_k: int = 5,
        category_id: uuid.UUID | None = None,
        user_role: str = "member",
        stream: bool = False,
    ) -> dict[str, Any]:
        """RAG 问答 — 检索 + 角色化生成。"""
        if not self.embedding.is_available:
            return {
                "answer": "知识库问答功能暂未配置。请管理员在环境变量中设置 OPENAI_API_KEY 后重试。",
                "sources": [], "confidence": 0.0, "degraded": True,
            }

        chunks = await self.search(tenant_id=tenant_id, query=question, top_k=top_k)
        if not chunks:
            return {"answer": "抱歉，没有找到与该问题相关的知识。请尝试换个问法或上传相关文档。", "sources": [], "confidence": 0.0}

        context_parts = [f"[文档{i + 1}: {c['document_title']}]\n{c['content']}" for i, c in enumerate(chunks)]
        context = "\n\n---\n\n".join(context_parts)

        # 角色化 System Prompt (Layer 2.1)
        role_prompts = {
            "新人": "用户是刚加入 OPC 的新人。请用简洁的语言、带序号步骤的方式回答。避免术语，给出可照着做的操作指南。字数不超过 300 字。",
            "核心成员": "用户是 OPC 核心成员。请提供详细说明，包含规则、注意事项和最佳实践。可引用具体案例。",
            "主理人": "用户是 OPC 分社主理人。请提供决策建议、风险评估和跨城市对比数据。回答应具备战略视角。",
        }
        role_instruction = role_prompts.get(user_role, role_prompts["核心成员"])

        system_prompt = f"""你是 OPC 平台的知识助手。{role_instruction}

规则:
1. 只使用提供的文档内容回答，不要编造信息
2. 如果文档内容不足以回答问题，请明确说明
3. 回答时标注引用来源，如 [文档1]、[文档2]
4. 使用中文回答"""

        user_prompt = f"## 相关文档内容\n\n{context}\n\n## 用户问题\n\n{question}\n\n请基于以上文档内容回答问题。"

        try:
            response = await self.llm_client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            answer = response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            answer = f"回答生成失败: {e}"

        sources = [{
            "document_id": c["document_id"],
            "document_title": c["document_title"],
            "chunk_index": c.get("chunk_index", 0),
            "score": c["score"],
        } for c in chunks]

        avg_score = sum(c["score"] for c in chunks) / len(chunks) if chunks else 0

        return {
            "answer": answer,
            "sources": sources,
            "chunks": chunks,
            "confidence": round(avg_score, 4),
        }


# ========== 全文搜索 (pg_trgm) ==========
async def fulltext_search(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    query: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list, int]:
    """全文搜索文档 (基于 PostgreSQL pg_trgm)"""
    from sqlalchemy import func, select, or_
    from app.modules.knowledge.models import KnowledgeDocument

    conditions = [
        KnowledgeDocument.tenant_id == tenant_id,
        KnowledgeDocument.status == "ready",
        KnowledgeDocument.is_deleted == False,
    ]
    like = f"%{query}%"
    conditions.append(KnowledgeDocument.title.ilike(like))

    total = await db.scalar(select(func.count(KnowledgeDocument.id)).where(*conditions))
    docs = (await db.execute(
        select(KnowledgeDocument).where(*conditions)
        .order_by(KnowledgeDocument.updated_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return list(docs), total or 0
