"""
认证 API

POST /api/v1/auth/login       — 用户名密码登录
POST /api/v1/auth/refresh     — 刷新 Token
POST /api/v1/auth/logout      — 登出
POST /api/v1/auth/register    — 注册新租户 + 管理员
GET  /api/v1/auth/me          — 当前用户信息
"""

from fastapi import APIRouter, Depends, Request, status

from app.core.database import get_db
from app.core.rate_limit import RATE_AUTH_LOGIN, RATE_AUTH_REGISTER, RATE_AUTH_REFRESH, limiter
from app.core.security import TokenPayload, get_current_user
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserInfo,
)
from app.modules.auth.service import (
    get_user_info,
    login,
    logout,
    refresh_access_token,
    register,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
@limiter.limit(RATE_AUTH_LOGIN)
async def login_endpoint(req: LoginRequest, request: Request, db=Depends(get_db)):
    """登录并返回 JWT Token 对"""
    result = await login(
        db,
        tenant_slug=req.tenant_slug,
        username=req.username,
        password=req.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    return result


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_AUTH_REGISTER)
async def register_endpoint(req: RegisterRequest, request: Request, db=Depends(get_db)):
    """注册新企业 + 管理员账号，返回 Token"""
    result = await register(
        db,
        tenant_name=req.tenant_name,
        tenant_slug=req.tenant_slug,
        username=req.username,
        password=req.password,
        email=req.email,
        display_name=req.display_name,
        ip_address=request.client.host if request.client else None,
    )

    # 事件驱动: 新成员注册 → 自动生成欢迎内容
    try:
        import asyncio as _asyncio
        _asyncio.create_task(_auto_welcome_new_member(
            tenant_slug=req.tenant_slug,
            username=req.username,
            display_name=req.display_name or req.username,
        ))
    except Exception:
        pass  # 欢迎生成失败不影响注册

    return result


async def _auto_welcome_new_member(tenant_slug: str, username: str, display_name: str):
    """自动为新成员生成欢迎内容"""
    try:
        from app.modules.skill.executor import executor
        result = await executor.execute(
            "send_notification",
            {
                "to_user_ids": [],  # 广播给所有成员
                "title": f"🎉 欢迎新成员 {display_name}",
                "body": f"欢迎 @{username} 加入 {tenant_slug}！\n\n新人报到，来打个招呼吧 👋",
                "urgency": "normal",
            },
            user_permissions=["notification:send"],
        )
        import logging
        logging.getLogger("opc.events").info(f"Welcome notification sent for {username}")
    except Exception as e:
        import logging
        logging.getLogger("opc.events").warning(f"Welcome generation failed: {e}")


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(RATE_AUTH_REFRESH)
async def refresh_endpoint(req: RefreshRequest, db=Depends(get_db)):
    """用 Refresh Token 换取新的 Token 对 (旧 Token 即时吊销)"""
    result = await refresh_access_token(db, req.refresh_token)
    return result


@router.post("/logout")
async def logout_endpoint(
    request: Request,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """登出：吊销 Refresh Token + Access Token 加入黑名单"""
    # 从 Authorization Header 提取当前 token
    auth_header = request.headers.get("Authorization", "")
    access_token = auth_header[len("Bearer "):] if auth_header.startswith("Bearer ") else ""
    result = await logout(db, current_user.sub, access_token)
    return result


@router.get("/me", response_model=UserInfo)
async def me_endpoint(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取当前登录用户的完整信息 (角色、权限)"""
    return await get_user_info(db, current_user.sub, current_user.tenant_id)
