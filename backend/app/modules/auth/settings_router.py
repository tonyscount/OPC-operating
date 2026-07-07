"""LLM 设置 API — 用户自助配置 API Key"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.security import TokenPayload, get_current_user
from app.core.settings_manager import manager

router = APIRouter()


class LLMSettings(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    provider: str = ""


@router.post("/llm")
async def update_llm(data: LLMSettings, _=Depends(get_current_user)):
    """保存 LLM 配置 → 内存立即生效 + 异步写 .env"""
    cfg = manager.update(**data.model_dump(exclude_none=True, exclude_unset=True))
    return {
        "message": "设置已应用",
        "provider": cfg.provider,
        "model": cfg.model,
        "base_url": cfg.base_url,
        "key_preview": _mask(cfg.api_key),
        "is_configured": cfg.is_configured,
    }


@router.get("/llm")
async def get_llm(_=Depends(get_current_user)):
    """查看当前 LLM 配置 (API Key 脱敏)"""
    cfg = manager.get_config()
    return {
        "provider": cfg.provider,
        "model": cfg.model,
        "base_url": cfg.base_url,
        "key_preview": _mask(cfg.api_key),
        "is_configured": cfg.is_configured,
    }


def _mask(key: str) -> str:
    if not key or len(key) < 12: return "(未配置)"
    return key[:8] + "****" + key[-4:]
