"""
ChromaDB 向量存储 — 替代 pgvector，纯 Python，零编译。

架构:
  - ChromaDB Client (持久化到本地目录)
  - 每个租户一个 Collection: "tenant_{tenant_id}"
  - 文档分块存储: (id, content, embedding, metadata)
"""

import logging
import uuid
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

logger = logging.getLogger("opc.vector_store")


def _sanitize_meta(meta: dict) -> dict:
    """递归转换所有值为字符串, 防止 ChromaDB 返回 UUID 对象"""
    result = {}
    for k, v in (meta or {}).items():
        if isinstance(v, uuid.UUID):
            result[k] = str(v)
        elif isinstance(v, dict):
            result[k] = _sanitize_meta(v)
        elif isinstance(v, list):
            result[k] = [str(x) if isinstance(x, uuid.UUID) else x for x in v]
        else:
            result[k] = v
    return result


class VectorStore:
    """ChromaDB 向量存储管理器"""

    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def client(self) -> chromadb.Client:
        if self._client is None:
            persist_dir = Path(settings.BASE_DIR) / "chroma_data"
            persist_dir.mkdir(exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(persist_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            logger.info(f"ChromaDB initialized at {persist_dir}")
        return self._client

    def get_collection(self, tenant_id: str) -> chromadb.Collection:
        """获取租户专属 Collection (禁用内置 embedding, 我们用自己的)"""
        name = f"tenant_{tenant_id}"
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,  # 禁用 ChromaDB 自带模型下载
        )

    def add_chunks(
        self,
        tenant_id: str,
        chunks: list[dict],
        embeddings: list[list[float]],
    ) -> list[str]:
        """
        批量添加文档块到向量存储。

        参数:
          tenant_id: 租户ID
          chunks: [{"id": str, "content": str, "document_id": str, "document_title": str, "chunk_index": int}, ...]
          embeddings: [[float, ...], ...]
        """
        if not chunks:
            return []

        collection = self.get_collection(tenant_id)

        ids = [str(c["id"]) for c in chunks]
        documents = [str(c["content"]) for c in chunks]
        metadatas = []
        for c in chunks:
            meta = {}
            for k, v in {
                "document_id": c.get("document_id", ""),
                "document_title": c.get("document_title", ""),
                "chunk_index": c.get("chunk_index", 0),
            }.items():
                meta[k] = str(v) if not isinstance(v, (int, float)) else v
            metadatas.append(meta)

        kwargs = {"ids": ids, "documents": documents, "metadatas": metadatas}
        if embeddings:
            kwargs["embeddings"] = embeddings
        collection.add(**kwargs)
        logger.info(f"Added {len(chunks)} chunks to tenant_{tenant_id}")
        return ids

    def search(
        self,
        tenant_id: str,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict | None = None,
    ) -> list[dict]:
        """向量相似度搜索。所有返回值转为纯字符串/数字，避免 UUID 序列化问题。"""
        try:
            return self._do_search(tenant_id, query_embedding, top_k, where)
        except Exception as e:
            logger.warning("Vector search failed, returning empty: %s", e)
            return []

    def _do_search(self, tenant_id, query_embedding, top_k, where):
        collection = self.get_collection(tenant_id)
        if collection.count() == 0:
            return []

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        items = []
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i] if results["distances"] else 0
            score = 1.0 - distance
            meta = _sanitize_meta(results["metadatas"][0][i]) if results["metadatas"] else {}

            items.append({
                "id": str(results["ids"][0][i]),
                "content": str(results["documents"][0][i]) if results["documents"] else "",
                "document_id": str(meta.get("document_id", "")),
                "document_title": str(meta.get("document_title", "")),
                "chunk_index": int(meta.get("chunk_index", 0) or 0),
                "score": round(score, 4),
            })

        return items

    def delete_document(self, tenant_id: str, document_id: str) -> int:
        """删除某个文档的所有向量块"""
        collection = self.get_collection(tenant_id)
        try:
            results = collection.get(
                where={"document_id": document_id},
                include=[],
            )
            if results["ids"]:
                collection.delete(ids=results["ids"])
                logger.info(f"Deleted {len(results['ids'])} chunks for doc {document_id}")
                return len(results["ids"])
        except Exception as e:
            logger.warning(f"Failed to delete chunks for doc {document_id}: {e}")
        return 0

    def count(self, tenant_id: str) -> int:
        """统计某租户的向量块数量"""
        return self.get_collection(tenant_id).count()

    def total_count(self) -> int:
        """统计所有租户的向量块总数"""
        total = 0
        for coll in self.client.list_collections():
            try:
                total += coll.count()
            except Exception:
                pass
        return total


# 全局单例
vector_store = VectorStore()
