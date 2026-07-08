"""
多租户模块 — 业务逻辑层

所有写操作自动注入 tenant_id 过滤，防止跨租户数据泄漏。
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_tenant_context
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.core.security import hash_password
from app.modules.tenant.models import Organization, Role, Tenant, User, UserRole

# ============================================================
# 租户
# ============================================================


async def create_tenant(db: AsyncSession, *, name: str, slug: str, plan: str = "free") -> Tenant:
    """创建新租户 + 自动创建默认角色"""
    # 检查 slug 唯一性
    existing = await db.execute(select(Tenant).where(Tenant.slug == slug))
    if existing.scalar_one_or_none():
        raise ConflictException(f"租户标识 '{slug}' 已存在")

    tenant = Tenant(name=name, slug=slug, plan=plan)
    db.add(tenant)
    await db.flush()  # 获取 tenant.id

    # 自动创建 4 个默认角色
    default_roles = [
        Role(
            tenant_id=tenant.id,
            name="管理员",
            description="拥有所有权限",
            permissions=[
                "tenant:manage", "org:manage", "user:manage", "role:manage",
                "knowledge:*", "agent:*", "skill:*", "search:*",
                "social:*", "schedule:*", "trade:*", "notification:*",
            ],
            is_system=True,
        ),
        Role(
            tenant_id=tenant.id,
            name="编辑",
            description="内容编辑与管理",
            permissions=[
                "knowledge:*", "social:write", "trade:write",
                "search:read", "notification:send",
            ],
            is_system=True,
        ),
        Role(
            tenant_id=tenant.id,
            name="成员",
            description="基础访问权限",
            permissions=[
                "knowledge:read", "agent:execute", "search:read",
                "social:read", "social:write",
            ],
            is_system=True,
        ),
        Role(
            tenant_id=tenant.id,
            name="访客",
            description="只读访问",
            permissions=["knowledge:read", "search:read", "social:read"],
            is_system=True,
        ),
    ]
    db.add_all(default_roles)
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    """获取租户信息"""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise NotFoundException("租户不存在")
    return tenant


async def get_tenant_by_slug(db: AsyncSession, slug: str) -> Tenant | None:
    """通过 slug 查找租户"""
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    return result.scalar_one_or_none()


async def update_tenant(db: AsyncSession, tenant_id: uuid.UUID, **kwargs) -> Tenant:
    tenant = await get_tenant(db, tenant_id)
    for k, v in kwargs.items():
        if v is not None:
            setattr(tenant, k, v)
    await db.commit()
    await db.refresh(tenant)
    return tenant


# ============================================================
# 组织
# ============================================================


async def create_org(
    db: AsyncSession, tenant_id: uuid.UUID, *, name: str, code: str | None = None,
    parent_id: uuid.UUID | None = None, sort_order: int = 0,
) -> Organization:
    """创建组织/部门。如果 parent_id 非空，会校验父组织属于同租户"""
    if parent_id:
        parent = await _get_org(db, tenant_id, parent_id)
        if not parent:
            raise NotFoundException("父组织不存在")

    org = Organization(
        tenant_id=tenant_id, name=name, code=code,
        parent_id=parent_id, sort_order=sort_order,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


async def get_org_tree(db: AsyncSession, tenant_id: uuid.UUID) -> list[Organization]:
    """获取组织树 (从根节点开始)"""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Organization)
        .where(Organization.tenant_id == tenant_id, Organization.parent_id.is_(None))
        .options(
            selectinload(Organization.children).selectinload(Organization.children),
        )
        .order_by(Organization.sort_order)
    )
    return list(result.scalars().all())


async def update_org(db: AsyncSession, tenant_id: uuid.UUID, org_id: uuid.UUID, **kwargs) -> Organization:
    org = await _get_org(db, tenant_id, org_id)
    for k, v in kwargs.items():
        if v is not None:
            setattr(org, k, v)
    await db.commit()
    await db.refresh(org)
    return org


async def delete_org(db: AsyncSession, tenant_id: uuid.UUID, org_id: uuid.UUID) -> None:
    """删除组织 (如果有子组织或成员则拒绝)"""
    org = await _get_org(db, tenant_id, org_id)
    # 检查子组织
    child_count = await db.scalar(
        select(func.count(Organization.id)).where(Organization.parent_id == org_id)
    )
    if child_count:
        raise ValidationException("该组织下还有子部门，请先删除子部门")
    # 检查成员
    member_count = await db.scalar(
        select(func.count(User.id)).where(User.org_id == org_id)
    )
    if member_count:
        raise ValidationException("该组织下还有成员，请先转移成员")
    await db.delete(org)
    await db.commit()


async def get_org_members(
    db: AsyncSession, tenant_id: uuid.UUID, org_id: uuid.UUID,
    page: int = 1, page_size: int = 20,
) -> tuple[list[User], int]:
    """获取组织成员列表 (分页)"""
    org = await _get_org(db, tenant_id, org_id)
    query = select(User).where(User.tenant_id == tenant_id, User.org_id == org_id)
    count_query = select(func.count(User.id)).where(
        User.tenant_id == tenant_id, User.org_id == org_id
    )
    total = await db.scalar(count_query)
    users = (await db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return list(users), total


async def _get_org(db: AsyncSession, tenant_id: uuid.UUID, org_id: uuid.UUID) -> Organization:
    result = await db.execute(
        select(Organization).where(
            Organization.id == org_id,
            Organization.tenant_id == tenant_id,
        )
    )
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundException("组织不存在")
    return org


# ============================================================
# 用户 (管理端)
# ============================================================


async def create_user(
    db: AsyncSession, tenant_id: uuid.UUID, *, username: str,
    password: str, email: str | None = None, phone: str | None = None,
    display_name: str | None = None, org_id: uuid.UUID | None = None,
    role_ids: list[uuid.UUID] | None = None,
) -> User:
    """创建用户并分配角色"""
    # 检查用户名唯一性
    existing = await db.scalar(
        select(User).where(User.tenant_id == tenant_id, User.username == username)
    )
    if existing:
        raise ConflictException(f"用户名 '{username}' 已存在")

    user = User(
        tenant_id=tenant_id,
        org_id=org_id,
        username=username,
        password_hash=hash_password(password),
        email=email,
        phone=phone,
        display_name=display_name or username,
    )
    db.add(user)
    await db.flush()

    # 分配角色
    if role_ids:
        for rid in role_ids:
            # 校验角色属于该租户
            role = await _get_role(db, tenant_id, rid)
            db.add(UserRole(user_id=user.id, role_id=rid))

    await db.commit()
    await db.refresh(user)
    return user


async def list_users(
    db: AsyncSession, tenant_id: uuid.UUID, *, keyword: str | None = None,
    org_id: uuid.UUID | None = None, status: str | None = None,
    page: int = 1, page_size: int = 20,
) -> tuple[list[User], int]:
    """用户列表 (带搜索和筛选)"""
    conditions = [User.tenant_id == tenant_id]
    if keyword:
        like = f"%{keyword}%"
        conditions.append(
            (User.username.ilike(like)) |
            (User.email.ilike(like)) |
            (User.phone.ilike(like)) |
            (User.display_name.ilike(like))
        )
    if org_id:
        conditions.append(User.org_id == org_id)
    if status:
        conditions.append(User.status == status)

    query = select(User).where(*conditions).options(selectinload(User.roles).selectinload(UserRole.role))
    count_query = select(func.count(User.id)).where(*conditions)

    total = await db.scalar(count_query)
    users = (await db.execute(
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return list(users), total


async def get_user(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User:
    result = await db.execute(
        select(User)
        .where(User.id == user_id, User.tenant_id == tenant_id)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException("用户不存在")
    return user


async def get_user_by_username(db: AsyncSession, tenant_id: uuid.UUID, username: str) -> User | None:
    result = await db.execute(
        select(User)
        .where(User.tenant_id == tenant_id, User.username == username)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    return result.scalar_one_or_none()


async def update_user(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID, **kwargs) -> User:
    user = await get_user(db, tenant_id, user_id)
    for k, v in kwargs.items():
        if v is not None:
            setattr(user, k, v)
    await db.commit()
    await db.refresh(user)
    return user


async def assign_roles(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID, role_ids: list[uuid.UUID],
) -> User:
    """重置用户的角色列表"""
    user = await get_user(db, tenant_id, user_id)
    # 删除旧角色
    from sqlalchemy import delete
    await db.execute(
        delete(UserRole).where(UserRole.user_id == user_id)
    )
    # 分配新角色
    for rid in role_ids:
        await _get_role(db, tenant_id, rid)
        db.add(UserRole(user_id=user_id, role_id=rid))
    await db.commit()
    await db.refresh(user)
    return user


# ============================================================
# 角色
# ============================================================


async def create_role(
    db: AsyncSession, tenant_id: uuid.UUID, *, name: str,
    description: str | None = None, permissions: list[str] | None = None,
) -> Role:
    existing = await db.scalar(
        select(Role).where(Role.tenant_id == tenant_id, Role.name == name)
    )
    if existing:
        raise ConflictException(f"角色 '{name}' 已存在")

    role = Role(
        tenant_id=tenant_id, name=name, description=description,
        permissions=permissions or [],
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


async def list_roles(db: AsyncSession, tenant_id: uuid.UUID) -> list[Role]:
    result = await db.execute(
        select(Role).where(Role.tenant_id == tenant_id).order_by(Role.created_at)
    )
    return list(result.scalars().all())


async def update_role(db: AsyncSession, tenant_id: uuid.UUID, role_id: uuid.UUID, **kwargs) -> Role:
    role = await _get_role(db, tenant_id, role_id)
    for k, v in kwargs.items():
        if v is not None:
            setattr(role, k, v)
    await db.commit()
    await db.refresh(role)
    return role


async def delete_role(db: AsyncSession, tenant_id: uuid.UUID, role_id: uuid.UUID) -> None:
    role = await _get_role(db, tenant_id, role_id)
    if role.is_system:
        raise ForbiddenException("系统内置角色不可删除")
    await db.delete(role)
    await db.commit()


async def _get_role(db: AsyncSession, tenant_id: uuid.UUID, role_id: uuid.UUID) -> Role:
    result = await db.execute(
        select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise NotFoundException("角色不存在")
    return role
