"""
认证与安全模块。

- JWT Token 生成 / 验证
- 密码哈希 (bcrypt)
- 租户上下文提取
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from app.config import settings
from app.core.database import set_tenant_context

# ========== OAuth2 配置 ==========
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ========== JWT Payload ==========
class TokenPayload(BaseModel):
    sub: str  # user_id
    tenant_id: str
    org_id: str | None = None
    roles: list[str] = []
    exp: int


# ========== JWT 工具 ==========
def create_access_token(
    user_id: str | UUID,
    tenant_id: str | UUID,
    org_id: str | UUID | None = None,
    roles: list[str] | None = None,
) -> str:
    """生成访问 Token (短期)"""
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "org_id": str(org_id) if org_id else None,
        "roles": roles or [],
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str | UUID) -> str:
    """生成刷新 Token (长期)"""
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc)
        + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> TokenPayload:
    """解析并验证 Token"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token 无效")


# ========== 密码哈希 ==========
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


# ========== FastAPI 依赖: 获取当前用户 ==========
async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
) -> TokenPayload:
    """
    依赖注入: 从请求中解析当前登录用户，并设置租户上下文。

    用法:
        @router.get("/me")
        async def me(current_user = Depends(get_current_user)):
            return current_user
    """
    if token is None:
        # 尝试从 query param 获取 (WebSocket 场景)
        token = request.query_params.get("token")

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)

    # 检查 token 是否在黑名单中 (登出后即时失效)
    import hashlib
    from app.core.database import async_session_factory
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    async with async_session_factory() as check_db:
        from sqlalchemy import select
        from app.modules.auth.models import TokenBlacklist
        blacklisted = await check_db.scalar(
            select(TokenBlacklist.id).where(TokenBlacklist.token_hash == token_hash)
        )
        if blacklisted is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token 已吊销",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 将租户上下文注入到当前协程
    set_tenant_context(payload.tenant_id)

    # 存储到 request.state 方便后续使用
    request.state.user_id = payload.sub
    request.state.tenant_id = payload.tenant_id
    request.state.org_id = payload.org_id

    return payload


# ========== FastAPI 依赖: 可选认证 (不强制登录) ==========
async def get_optional_user(
    token: str | None = Depends(oauth2_scheme),
) -> TokenPayload | None:
    """不强制登录，如果提供了有效 Token 就解析，否则返回 None"""
    if token is None:
        return None
    try:
        return decode_token(token)
    except HTTPException:
        return None


# ========== 权限检查 ==========
class PermissionChecker:
    """
    权限检查依赖工厂 —— 从数据库查询当前用户角色的权限并校验。

    用法:
        require_perm = PermissionChecker("knowledge:upload")
        @router.post("/knowledge/documents")
        async def upload(doc, current_user = Depends(get_current_user),
                         _ = Depends(require_perm)):
            ...

    支持通配符匹配: "knowledge:*" 匹配 "knowledge:upload", "knowledge:read" 等。
    """

    def __init__(self, permission: str):
        self.permission = permission

    async def __call__(
        self,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> bool:
        from uuid import UUID

        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.core.database import async_session_factory
        from app.modules.tenant.models import User, UserRole

        # 从数据库查询用户实际拥有的权限 (避免只用 JWT 中的过期信息)
        async with async_session_factory() as db:
            result = await db.execute(
                select(User)
                .where(User.id == UUID(current_user.sub))
                .options(selectinload(User.roles).selectinload(UserRole.role))
            )
            user = result.scalar_one_or_none()
            if not user or user.status != "active":
                from app.core.exceptions import ForbiddenException
                raise ForbiddenException("用户不可用")

            all_permissions: set[str] = set()
            for ur in user.roles:
                for perm in ur.role.permissions:
                    all_permissions.add(perm)

            # 检查是否拥有所需权限 (支持通配符)
            if not _match_permission(self.permission, all_permissions):
                from app.core.exceptions import ForbiddenException
                raise ForbiddenException(
                    f"需要权限 '{self.permission}'，当前无此权限"
                )

        return True


def _match_permission(required: str, granted: set[str]) -> bool:
    """权限匹配 (支持通配符)"""
    if required in granted:
        return True
    # 通配符匹配: "knowledge:*" 匹配 "knowledge:read"
    parts = required.split(":")
    for i in range(len(parts), 0, -1):
        wildcard = ":".join(parts[:i]) + ":*"
        if wildcard in granted:
            return True
    # 全局通配符
    if "*" in granted or "*:*" in granted:
        return True
    return False
