"""
认证模块 — 业务逻辑层

登录流程:
  1. 根据 tenant_slug 定位租户
  2. 在该租户下验证用户名密码
  3. 获取用户角色和权限
  4. 生成 JWT (含 tenant_id, org_id, roles)
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.database import set_tenant_context
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.modules.auth.models import LoginLog, RefreshToken, TokenBlacklist
from app.modules.tenant.models import Role, User, UserRole
from app.modules.tenant.schemas import UserCreate
from app.modules.tenant.service import create_tenant as tenant_create
from app.modules.tenant.service import create_user as tenant_user_create
from app.modules.tenant.service import get_tenant_by_slug


# ========== 登录 ==========
async def login(
    db: AsyncSession,
    tenant_slug: str,
    username: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    """登录并返回 Token 对"""
    # 1. 找租户
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if not tenant:
        raise HTTPException(status_code=401, detail="租户不存在")

    if tenant.status != "active":
        raise HTTPException(status_code=403, detail="租户已被停用")

    # 2. 在该租户下查用户
    result = await db.execute(
        select(User)
        .where(User.tenant_id == tenant.id, User.username == username)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        await _log_login(db, None, tenant.id, ip_address, user_agent, success=False, reason="用户名或密码错误")
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if user.status != "active":
        await _log_login(db, user.id, tenant.id, ip_address, user_agent, success=False, reason=f"用户状态: {user.status}")
        raise HTTPException(status_code=403, detail=f"账号已被{'禁用' if user.status == 'disabled' else '封禁'}")

    # 3. 提取角色和权限
    role_names = [ur.role.name for ur in user.roles]
    permissions: list[str] = []
    for ur in user.roles:
        permissions.extend(ur.role.permissions)

    # 4. 生成 Token
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=tenant.id,
        org_id=user.org_id,
        roles=role_names,
    )
    refresh_token = create_refresh_token(user.id, tenant.id)

    # 5. 清理旧 Token + 存储新 Token
    await db.execute(
        text("DELETE FROM refresh_tokens WHERE user_id = :uid"), {"uid": user.id}
    )
    token_hash = _hash_token(refresh_token)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    await _log_login(db, user.id, tenant.id, ip_address, user_agent, success=True)
    await db.commit()

    # 7. 设置租户上下文 (后续数据库操作自动带租户过滤)
    set_tenant_context(str(tenant.id))

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# ========== 注册 ==========
async def register(db: AsyncSession, *, tenant_name: str, tenant_slug: str,
                   username: str, password: str, email: str | None = None,
                   display_name: str | None = None,
                   ip_address: str | None = None) -> dict:
    """注册新租户 + 管理员用户，一步完成"""
    # 1. 创建租户 (自动创建 4 个默认角色)
    tenant = await tenant_create(db, name=tenant_name, slug=tenant_slug)

    # 2. 找到管理员角色
    result = await db.execute(
        select(Role).where(Role.tenant_id == tenant.id, Role.name == "管理员")
    )
    admin_role = result.scalar_one_or_none()
    if not admin_role:
        raise HTTPException(status_code=500, detail="默认角色创建失败")

    # 3. 创建管理员用户
    user = await tenant_user_create(
        db,
        tenant_id=tenant.id,
        username=username,
        password=password,
        email=email,
        display_name=display_name or username,
        role_ids=[admin_role.id],
    )

    # 4. 直接登录
    set_tenant_context(str(tenant.id))

    access_token = create_access_token(
        user_id=user.id,
        tenant_id=tenant.id,
        org_id=user.org_id,
        roles=["管理员"],
    )
    refresh_token = create_refresh_token(user.id, tenant.id)

    # 清理旧 Token
    await db.execute(
        text("DELETE FROM refresh_tokens WHERE user_id = :uid"), {"uid": user.id}
    )
    token_hash = _hash_token(refresh_token)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    await _log_login(db, user.id, tenant.id, ip_address, None, success=True)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# ========== Token 刷新 ==========
async def refresh_access_token(db: AsyncSession, refresh_token: str) -> dict:
    """用 Refresh Token 换新的 Access Token"""
    try:
        payload = decode_token(refresh_token)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    if payload.type != "refresh":
        raise HTTPException(status_code=401, detail="Token 类型错误")

    token_hash = _hash_token(refresh_token)

    # 检查 Refresh Token 是否在白名单中且未被吊销
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
        )
    )
    stored = result.scalar_one_or_none()
    if not stored:
        raise HTTPException(status_code=401, detail="Token 已被吊销或不存在")

    # 检查用户状态
    user_id = uuid.UUID(payload.sub)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.status != "active":
        raise HTTPException(status_code=403, detail="账号不可用")

    # 获取角色权限
    result = await db.execute(
        select(User).where(User.id == user_id).options(
            selectinload(User.roles).selectinload(UserRole.role)
        )
    )
    user = result.scalar_one()
    role_names = [ur.role.name for ur in user.roles]

    # 吊销旧 Token (直接删除, 避免 UNIQUE 冲突)
    await db.delete(stored)
    await db.flush()

    # 签发新 Token
    new_access = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        org_id=user.org_id,
        roles=role_names,
    )
    new_refresh = create_refresh_token(user.id, payload.tenant_id)

    new_hash = _hash_token(new_refresh)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=new_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    await db.commit()

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# ========== 登出 ==========
async def logout(db: AsyncSession, user_id: uuid.UUID, access_token: str):
    """登出: 将 Access Token 加入黑名单，吊销所有 Refresh Token"""
    # 吊销用户所有未吊销的 Refresh Token
    from sqlalchemy import update
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)
        .values(revoked=True)
    )

    # Access Token 加入黑名单 (防止在有效期内继续使用)
    token_hash = _hash_token(access_token)
    existing = await db.scalar(
        select(TokenBlacklist).where(TokenBlacklist.token_hash == token_hash)
    )
    if not existing:
        db.add(TokenBlacklist(
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        ))

    await db.commit()
    return {"message": "已登出"}


# ========== 获取当前用户详情 ==========
async def get_user_info(db: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID) -> dict:
    """获取当前用户完整信息 (用于 /me 接口)"""
    result = await db.execute(
        select(User)
        .where(User.id == user_id, User.tenant_id == tenant_id)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 获取租户名
    from app.modules.tenant.models import Tenant
    tenant = await db.get(Tenant, tenant_id)

    role_names = [ur.role.name for ur in user.roles]
    all_permissions: list[str] = []
    for ur in user.roles:
        all_permissions.extend(ur.role.permissions)

    return {
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "tenant_name": tenant.name if tenant else "",
        "org_id": str(user.org_id) if user.org_id else None,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "roles": role_names,
        "permissions": list(set(all_permissions)),
    }


# ========== 辅助函数 ==========
def _hash_token(token: str) -> str:
    """SHA256 哈希 Token (用于存储)"""
    return hashlib.sha256(token.encode()).hexdigest()


async def _log_login(
    db: AsyncSession,
    user_id: uuid.UUID | None,
    tenant_id: uuid.UUID,
    ip: str | None,
    ua: str | None,
    success: bool,
    reason: str | None = None,
):
    db.add(LoginLog(
        user_id=user_id or uuid.UUID(int=0),
        tenant_id=tenant_id,
        ip_address=ip,
        user_agent=ua,
        success=success,
        fail_reason=reason,
    ))
