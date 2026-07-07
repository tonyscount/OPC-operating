"""
Skill: 搜索知识库 (混合检索: 向量 + BM25 关键词)

Agent 调用此 Skill 在知识库中检索相关文档内容。
向量检索和 BM25 关键词检索并行执行，结果合并去重排序。
"""

from app.modules.skill.registry import skill_registry


@skill_registry.register(
    name="search_knowledge",
    display_name="搜索知识库",
    description="在知识库中搜索与查询相关的文档内容，同时使用语义(向量)和关键词(BM25)检索，返回最匹配的文本块及其来源",
    parameters_schema={
        "query": {"type": "string", "description": "搜索关键词或自然语言问题", "required": True},
        "top_k": {"type": "integer", "description": "返回的最相关文本块数量", "default": 5},
    },
    timeout=30,
    required_permissions=["knowledge:read"],
    is_builtin=True,
)
async def search_knowledge(params: dict, context: dict) -> dict:
    """
    混合检索: 向量 + BM25 并行 → 合并去重排序。

    context: { user_id, tenant_id, trace_id }
    """
    from uuid import UUID
    from app.modules.knowledge.retrieval import RAGService
    from app.modules.knowledge.vector_store import vector_store
    from app.modules.knowledge.bm25 import BM25, merge_results, rerank_with_query

    query = params.get("query", "")
    top_k = params.get("top_k", 5)
    tenant_id = context.get("tenant_id")

    if not tenant_id:
        return {"query": query, "total_found": 0, "results": [], "error": "缺少租户上下文"}

    # 并行: 向量检索 + BM25 检索
    import asyncio

    async def vector_search():
        try:
            rag = RAGService()
            return await rag.search(tenant_id=UUID(tenant_id), query=query, top_k=top_k)
        except Exception as e:
            import logging
            logging.getLogger("opc.skill.search").warning("Vector search degraded: %s", e)
            return []

    async def keyword_search():
        """BM25 关键词检索 — 失败时优雅降级"""
        try:
            coll = vector_store.get_collection(str(tenant_id))
            if coll.count() == 0:
                return []
            all_data = coll.get(include=["documents", "metadatas"])
            if not all_data.get("ids"):
                return []
            bm25 = BM25()
            safe_metas = []
            for i, id_ in enumerate(all_data.get("ids", [])):
                sm = {}
                raw_meta = (all_data.get("metadatas") or [])[i] if i < len(all_data.get("metadatas") or []) else {}
                for k, v in (raw_meta or {}).items():
                    sm[k] = str(v) if v is not None else ""
                sm["id"] = str(id_)
                safe_metas.append(sm)
            docs = [str(d) for d in (all_data.get("documents") or [])]
            bm25.fit(documents=docs, metas=safe_metas)
            return bm25.search(query, top_k=top_k)
        except Exception as e:
            import logging
            logging.getLogger("opc.skill.search").warning("BM25 degraded: %s", e)
            return []

    vector_results, bm25_results = await asyncio.gather(
        vector_search(), keyword_search()
    )

    # 合并结果
    # 合并 + Reranker 重排序
    merged = merge_results(vector_results, bm25_results, top_k=max(top_k * 2, 10))
    merged = rerank_with_query(merged, query)[:top_k]

    results = []
    for c in merged:
        results.append({
            "document_title": c.get("document_title", ""),
            "content": c.get("content", "")[:500],
            "score": c.get("combined_score", c.get("score", 0)),
            "match_type": c.get("match_type", "semantic"),
        })

    return {
        "query": query,
        "total_found": len(results),
        "vector_count": len(vector_results),
        "keyword_count": len(bm25_results),
        "results": results,
    }
