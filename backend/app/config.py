"""
应用配置中心 —— 所有配置通过环境变量注入，pydantic-settings 管理。

使用方式:
    from app.config import settings
    print(settings.DATABASE_URL)
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ========== 应用 ==========
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = True
    APP_NAME: str = "OPC Platform"
    APP_VERSION: str = "0.1.0"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    # ========== 数据库 ==========
    DATABASE_URL: str = "postgresql+asyncpg://opc_user:opc_dev_password@localhost:5432/opc_platform"
    DATABASE_URL_SYNC: str = "postgresql://opc_user:opc_dev_password@localhost:5432/opc_platform"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # ========== Redis ==========
    REDIS_URL: str = "redis://localhost:6379/0"

    # ========== JWT ==========
    JWT_SECRET_KEY: str = "change-me-to-a-random-secret-at-least-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ========== LLM / AI ==========
    LLM_PROVIDER: Literal["openai", "deepseek", "qwen"] = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536

    # ========== 搜索 ==========
    SEARCH_API_KEY: str = ""
    SEARCH_API_BASE_URL: str = ""

    # ========== 飞书 ==========
    FEISHU_WEBHOOK_URL: str = ""

    # ========== 路径 ==========
    @property
    def BASE_DIR(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def SKILLS_DIR(self) -> Path:
        return self.BASE_DIR / "skills"

    def validate_critical(self) -> list[str]:
        """启动时校验关键配置，返回警告列表"""
        warnings = []

        # JWT 密钥
        if self.JWT_SECRET_KEY == "change-me-to-a-random-secret-at-least-32-chars":
            warnings.append("CRITICAL: JWT_SECRET_KEY 是默认占位值，请立即更换！")
        if len(self.JWT_SECRET_KEY) < 32:
            warnings.append("WARNING: JWT_SECRET_KEY 长度不足 32 字符")

        # 数据库密码
        if "YOUR_DB_PASSWORD" in self.DATABASE_URL:
            warnings.append("CRITICAL: DATABASE_URL 包含占位密码，请修改！")
        if "opc_dev_password" == self.DATABASE_URL.split(":")[-1].split("@")[0] and self.APP_ENV == "production":
            warnings.append("CRITICAL: 生产环境使用了开发数据库密码！")

        # LLM API Key
        if self.LLM_PROVIDER != "none" and self.OPENAI_API_KEY in ("", "sk-your-key-here", "sk-your-api-key-here"):
            warnings.append("WARNING: OPENAI_API_KEY 未配置，RAG/Agent 功能将不可用")

        # CORS
        if "*" in self.CORS_ORIGINS and self.APP_ENV == "production":
            warnings.append("CRITICAL: 生产环境 CORS 不允许使用通配符 *")

        # Feishu
        if self.APP_ENV == "production" and not self.FEISHU_WEBHOOK_URL:
            warnings.append("WARNING: 生产环境未配置飞书告警 Webhook")

        return warnings


settings = Settings()
