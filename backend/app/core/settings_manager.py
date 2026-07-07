"""
SettingsManager — 优先级: 内存缓存 > .env 文件

用户保存 API Key → 立即写入内存 (毫秒生效) + 异步持久化 .env
AI 调用模块直接读内存配置，无需重启服务。
"""

import asyncio
import logging
import re
import threading
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger("opc.settings")


@dataclass
class LLMConfig:
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    provider: str = "deepseek"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 20)


class SettingsManager:
    """全局配置管理器 — 内存优先，异步写盘"""

    def __init__(self):
        self._lock = threading.Lock()
        self._llm: LLMConfig = LLMConfig()

    def load_from_env(self):
        """启动时从 .env 加载初始配置"""
        from app.config import settings
        with self._lock:
            self._llm = LLMConfig(
                api_key=settings.OPENAI_API_KEY or "",
                base_url=settings.OPENAI_BASE_URL or "https://api.deepseek.com/v1",
                model=settings.LLM_MODEL or "deepseek-chat",
                provider=settings.LLM_PROVIDER or "deepseek",
            )
        logger.info(f"Settings loaded: provider={self._llm.provider} key={'***' if self._llm.is_configured else '(none)'}")

    def update(self, **kwargs) -> LLMConfig:
        """立即更新内存配置，异步写盘"""
        with self._lock:
            for k, v in kwargs.items():
                if v and hasattr(self._llm, k):
                    setattr(self._llm, k, v)
            config = self._llm

        # 异步持久化
        asyncio.create_task(self._persist_async())
        return config

    def get_config(self) -> LLMConfig:
        with self._lock:
            return self._llm

    async def _persist_async(self):
        """异步写入 .env 文件"""
        try:
            env_path = Path(__file__).resolve().parent.parent.parent / ".env"
            if not env_path.exists():
                return
            content = env_path.read_text(encoding="utf-8")
            with self._lock:
                cfg = self._llm
            content = self._replace(content, "OPENAI_API_KEY", cfg.api_key)
            content = self._replace(content, "OPENAI_BASE_URL", cfg.base_url)
            content = self._replace(content, "LLM_MODEL", cfg.model)
            content = self._replace(content, "LLM_PROVIDER", cfg.provider)
            env_path.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to persist settings: {e}")

    @staticmethod
    def _replace(content: str, key: str, value: str) -> str:
        pattern = rf"^{key}=.*$"
        replacement = f"{key}={value}"
        if re.search(pattern, content, re.MULTILINE):
            return re.sub(pattern, replacement, content, flags=re.MULTILINE)
        return content.rstrip() + f"\n{replacement}\n"


# 全局单例
manager = SettingsManager()
