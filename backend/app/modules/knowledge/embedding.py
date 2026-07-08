"""
嵌入服务 — 文本向量化。

三层策略 (按优先级):
  1. 远程 Embedding API (EMBEDDING_API_KEY 或 OPENAI_API_KEY 配了)
  2. 本地 BGE 模型 (fastembed, 无需任何外部 API)
  3. 优雅降级 (返回空列表，让调用方处理)

用法:
    svc = get_embedding_service()
    vec = await svc.embed_query("你好世界")
"""

import asyncio
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger("opc.embedding")


class EmbeddingService:
    """远程 Embedding API 服务 (OpenAI 兼容)"""

    def __init__(self):
        self.model = settings.EMBEDDING_MODEL
        self.dimensions = settings.EMBEDDING_DIMENSIONS
        self._client = None

    @property
    def is_available(self) -> bool:
        """远程 API Key 已配置时返回 True"""
        key = settings.EMBEDDING_EFFECTIVE_KEY
        return bool(key and key not in ("", "sk-your-key-here", "sk-change-me-to-your-real-key"))

    @property
    def client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=settings.EMBEDDING_EFFECTIVE_KEY,
                base_url=settings.EMBEDDING_EFFECTIVE_URL,
            )
        return self._client

    async def embed_text(self, text: str) -> list[float]:
        """单个文本向量化。失败时返回空列表"""
        embeddings = await self.embed_batch([text])
        if not embeddings:
            return []
        return embeddings[0]

    async def embed_batch(self, texts: list[str], batch_size: int = 20) -> list[list[float]]:
        """批量文本向量化。失败时返回空列表让调用方优雅降级。"""
        if not self.is_available:
            return []

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                response = await self.client.embeddings.create(
                    model=self.model, input=batch, dimensions=self.dimensions,
                    timeout=5,
                )
                all_embeddings.extend([d.embedding for d in response.data])
                logger.info(f"Embedded batch {i // batch_size + 1}: {len(batch)} texts")
            except Exception as e:
                logger.warning(f"Embedding failed for batch {i // batch_size + 1}: {e}")
                return []

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """查询向量化"""
        return await self.embed_text(query)


# ========== 本地 BGE 模型 (fastembed) ==========

class LocalEmbeddingService:
    """
    使用 fastembed 加载本地 ONNX 模型，纯 CPU 推理，无需任何外部 API。

    默认模型: BAAI/bge-small-zh-v1.5 (512维, ~100MB)
    首次运行自动下载模型到 ~/.cache/huggingface。

    国内网络加速:
        set HF_ENDPOINT=https://hf-mirror.com  # 使用镜像下载
        set HF_HUB_ENABLE_HF_TRANSFER=1        # 加速下载 (可选)
    离线模式:
        set HF_HUB_OFFLINE=1  # 跳过网络检查，直接用缓存
    """

    def __init__(self):
        self.model_name = settings.LOCAL_EMBEDDING_MODEL
        self.dimensions = 512  # bge-small-zh-v1.5 的维度
        self._model = None
        self._load_error: str | None = None

    @property
    def is_available(self) -> bool:
        """本地模型总是可用 (懒加载，首次调用时下载)"""
        return True

    def _ensure_model(self):
        """懒加载模型 (首次调用时下载，后续复用)"""
        if self._model is not None:
            return
        if self._load_error is not None:
            return  # 已经尝试过加载，失败了

        try:
            from fastembed import TextEmbedding

            # 国内用户: 尝试用镜像 (env 或代码层检测)
            import os
            if not os.environ.get("HF_ENDPOINT"):
                # 检测是否在国内网络 (HF 直连可能超时)
                pass  # 用户可自行设置 HF_ENDPOINT

            self._model = TextEmbedding(
                model_name=self.model_name,
                providers=["CPUExecutionProvider"],
            )
            # 触发模型加载，获取实际维度
            probe = list(self._model.embed(["probe"]))
            self.dimensions = len(probe[0])
            logger.info(
                f"Local embedding loaded: {self.model_name} "
                f"({self.dimensions}d)"
            )
        except Exception as e:
            self._load_error = str(e)
            self._model = None
            logger.error(
                f"Failed to load local embedding model '{self.model_name}': {e}\n"
                f"  国内用户请尝试: set HF_ENDPOINT=https://hf-mirror.com"
            )

    async def embed_text(self, text: str) -> list[float]:
        """单个文本向量化"""
        embeddings = await self.embed_batch([text])
        if not embeddings:
            return []
        return embeddings[0]

    async def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """批量文本向量化 (本地 ONNX 推理, 在 executor 中运行避免阻塞事件循环)"""
        if not texts:
            return []

        self._ensure_model()
        if self._model is None:
            return []

        def _run():
            results = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                embeddings = list(self._model.embed(batch))
                results.extend([e.tolist() for e in embeddings])
            return results

        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, _run)
        except Exception as e:
            logger.error(f"Local embedding failed: {e}")
            return []

    async def embed_query(self, query: str) -> list[float]:
        """查询向量化"""
        return await self.embed_text(query)


# ========== 工厂 ==========

def get_embedding_service():
    """
    自动选择 embedding 实现:
      - 有远程 API Key → EmbeddingService (远程)
      - 无任何 Key     → LocalEmbeddingService (本地 BGE)
    """
    remote = EmbeddingService()
    if remote.is_available:
        logger.info(f"Using remote embedding: {settings.EMBEDDING_EFFECTIVE_URL}/{remote.model}")
        return remote

    logger.info(f"Using local embedding: {settings.LOCAL_EMBEDDING_MODEL}")
    return LocalEmbeddingService()
