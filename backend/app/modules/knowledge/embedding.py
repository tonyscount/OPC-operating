"""
嵌入服务 — 文本向量化。

支持:
  - OpenAI text-embedding-3-small (默认)
  - 本地 BGE-M3 (通过兼容 API)
  - 批量嵌入以提高效率
"""

import asyncio
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger("opc.embedding")


class EmbeddingService:
    """文本嵌入服务 — API Key 缺失时优雅降级"""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = settings.EMBEDDING_MODEL
        self.dimensions = settings.EMBEDDING_DIMENSIONS
        self._client = None
        self._available = None  # None=未检查, True/False

    @property
    def is_available(self) -> bool:
        """API Key 已配置且 Provider 支持 embedding 时返回 True"""
        if self._available is not None:
            return self._available
        key = settings.OPENAI_API_KEY
        self._available = bool(key and key not in ("", "sk-your-key-here", "sk-change-me-to-your-real-key"))
        if not self._available:
            logger.warning("Embedding service unavailable: OPENAI_API_KEY not configured")
        else:
            logger.info(f"Embedding service enabled: {self.provider}/{self.model} ({self.dimensions}d)")
        return self._available

    @property
    def client(self):
        if not self.is_available:
            return None
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )
        return self._client

    async def embed_text(self, text: str) -> list[float]:
        """单个文本向量化。失败时返回空列表"""
        embeddings = await self.embed_batch([text])
        if not embeddings:
            return []
        return embeddings[0]

    async def embed_batch(self, texts: list[str], batch_size: int = 20) -> list[list[float]]:
        """批量文本向量化。API Key 缺失时返回空列表 + 日志告警。"""
        if not self.is_available:
            logger.warning("Embedding service unavailable: OPENAI_API_KEY not configured")
            return []  # 返回空列表，调用方应检查

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                response = await self.client.embeddings.create(
                    model=self.model, input=batch, dimensions=self.dimensions,
                    timeout=5,  # 快速失败, 不阻塞上传
                )
                batch_embeddings = [d.embedding for d in response.data]
                all_embeddings.extend(batch_embeddings)
                logger.info(f"Embedded batch {i // batch_size + 1}: {len(batch)} texts")
            except Exception as e:
                logger.error(f"Embedding failed for batch {i // batch_size + 1}: {e}")
                # 不假装成功，返回空列表让调用方优雅降级 (如返回"暂不支持"提示)
                return []

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """查询向量化 (与文档使用相同模型)"""
        return await self.embed_text(query)


# ========== 本地 BGE-M3 备用实现 ==========
class LocalEmbeddingService(EmbeddingService):
    """
    使用本地部署的 BGE-M3 模型 (通过兼容 OpenAI API 的服务)。

    需要在 .env 中设置:
        OPENAI_BASE_URL=http://localhost:8080/v1
        EMBEDDING_MODEL=bge-m3
        EMBEDDING_DIMENSIONS=1024
    """

    pass


# ========== 工厂 ==========
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
