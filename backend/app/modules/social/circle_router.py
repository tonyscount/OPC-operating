"""
圈子 API

POST   /circles            创建圈子
GET    /circles            圈子列表
GET    /circles/{id}       圈子详情
POST   /circles/{id}/join  加入圈子
POST   /circles/{id}/leave 退出圈子
GET    /circles/{id}/posts 圈子动态
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from app.core.database import get_db
from app.core.exceptions import ConflictException, NotFoundException
from app.core.security import TokenPayload, get_current_user
from app.modules.social.circle_models import Circle, CircleMember
from app.modules.social.models import SocialPost

router = APIRouter()


@router.post("/circles", status_code=status.HTTP_201_CREATED)
async def create_circle(
    name: str,
    slug: str,
    category: str = "general",
    description: str | None = None,
    icon_url: str | None = None,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """创建圈子"""
    tid = uuid.UUID(current_user.tenant_id)
    uid = uuid.UUID(current_user.sub)

    existing = await db.scalar(
        select(Circle).where(Circle.tenant_id == tid, Circle.slug == slug)
    )
    if existing:
        raise ConflictException("圈子标识已被使用")

    circle = Circle(
        tenant_id=tid, name=name, slug=slug,
        category=category, description=description,
        icon_url=icon_url, created_by=uid,
    )
    db.add(circle)
    await db.flush()

    # 创建者自动加入为 owner
    db.add(CircleMember(tenant_id=tid, circle_id=circle.id, user_id=uid, role="owner"))
    await db.commit()
    await db.refresh(circle)

    return {
        "id": str(circle.id), "name": circle.name, "slug": circle.slug,
        "category": circle.category, "member_count": 1,
    }


@router.get("/circles")
async def list_circles(
    category: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """圈子列表"""
    tid = uuid.UUID(current_user.tenant_id)
    conditions = [Circle.tenant_id == tid, Circle.is_deleted == False]
    if category:
        conditions.append(Circle.category == category)

    total = await db.scalar(select(func.count(Circle.id)).where(*conditions))
    circles = (await db.execute(
        select(Circle).where(*conditions)
        .order_by(Circle.member_count.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    items = [{
        "id": str(c.id), "name": c.name, "slug": c.slug,
        "category": c.category, "description": c.description,
        "icon_url": c.icon_url, "member_count": c.member_count,
        "post_count": c.post_count, "is_public": c.is_public,
    } for c in circles]
    return {"items": items, "total": total or 0, "page": page, "page_size": page_size}


@router.get("/circles/{circle_id}")
async def get_circle(
    circle_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """圈子详情"""
    circle = await db.get(Circle, circle_id)
    if not circle or circle.tenant_id != uuid.UUID(current_user.tenant_id):
        raise NotFoundException("圈子不存在")

    # 检查当前用户是否是成员
    uid = uuid.UUID(current_user.sub)
    membership = await db.scalar(
        select(CircleMember).where(
            CircleMember.circle_id == circle_id,
            CircleMember.user_id == uid,
            CircleMember.is_deleted == False,
        )
    )

    return {
        "id": str(circle.id), "name": circle.name, "slug": circle.slug,
        "category": circle.category, "description": circle.description,
        "icon_url": circle.icon_url, "cover_url": circle.cover_url,
        "member_count": circle.member_count, "post_count": circle.post_count,
        "is_public": circle.is_public,
        "is_member": membership is not None,
        "role": membership.role if membership else None,
        "created_at": circle.created_at.isoformat(),
    }


@router.post("/circles/{circle_id}/join")
async def join_circle(
    circle_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """加入圈子"""
    tid = uuid.UUID(current_user.tenant_id)
    uid = uuid.UUID(current_user.sub)

    circle = await db.get(Circle, circle_id)
    if not circle or circle.tenant_id != tid:
        raise NotFoundException("圈子不存在")

    existing = await db.scalar(
        select(CircleMember).where(
            CircleMember.circle_id == circle_id,
            CircleMember.user_id == uid,
            CircleMember.is_deleted == False,
        )
    )
    if existing:
        return {"message": "已是成员", "member_count": circle.member_count}

    db.add(CircleMember(tenant_id=tid, circle_id=circle_id, user_id=uid))
    circle.member_count += 1
    await db.commit()
    return {"message": "已加入", "member_count": circle.member_count}


@router.post("/circles/{circle_id}/leave")
async def leave_circle(
    circle_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """退出圈子 (owner 不能退出，需先转让或解散)"""
    uid = uuid.UUID(current_user.sub)

    circle = await db.get(Circle, circle_id)
    if not circle:
        raise NotFoundException("圈子不存在")

    membership = await db.scalar(
        select(CircleMember).where(
            CircleMember.circle_id == circle_id,
            CircleMember.user_id == uid,
            CircleMember.is_deleted == False,
        )
    )
    if not membership:
        return {"message": "不是成员"}

    if membership.role == "owner":
        raise ConflictException("圈主不能退出，请先转让圈子或解散圈子")

    membership.is_deleted = True
    circle.member_count = max(0, circle.member_count - 1)
    await db.commit()
    return {"message": "已退出", "member_count": circle.member_count}


@router.get("/circles/{circle_id}/posts")
async def circle_feed(
    circle_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """圈子动态"""
    tid = uuid.UUID(current_user.tenant_id)
    circle = await db.get(Circle, circle_id)
    if not circle or circle.tenant_id != tid:
        raise NotFoundException("圈子不存在")

    conditions = [
        SocialPost.tenant_id == tid,
        SocialPost.circle_id == circle_id,
        SocialPost.is_deleted == False,
    ]
    total = await db.scalar(select(func.count(SocialPost.id)).where(*conditions))
    posts = (await db.execute(
        select(SocialPost).where(*conditions)
        .order_by(SocialPost.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    items = [{
        "id": str(p.id), "content": p.content,
        "author_id": str(p.author_id),
        "is_pinned": p.is_pinned, "is_essence": p.is_essence,
        "like_count": p.like_count, "comment_count": p.comment_count,
        "view_count": p.view_count, "created_at": p.created_at.isoformat(),
    } for p in posts]
    return {"items": items, "total": total or 0, "page": page, "page_size": page_size}


# ============================================================
# 圈子管理 (owner/admin)
# ============================================================

async def _require_circle_admin(db, circle_id: uuid.UUID, user_id: uuid.UUID):
    """校验用户是圈子 owner/admin，返回 membership"""
    membership = await db.scalar(
        select(CircleMember).where(
            CircleMember.circle_id == circle_id,
            CircleMember.user_id == user_id,
            CircleMember.is_deleted == False,
        )
    )
    if not membership or membership.role not in ("owner", "admin"):
        from app.core.exceptions import ForbiddenException
        raise ForbiddenException("需要圈子管理员权限")
    return membership


@router.post("/circles/{circle_id}/posts/{post_id}/pin")
async def toggle_pin(
    circle_id: uuid.UUID,
    post_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """置顶/取消置顶"""
    await _require_circle_admin(db, circle_id, uuid.UUID(current_user.sub))
    post = await db.get(SocialPost, post_id)
    if not post or post.circle_id != circle_id:
        raise NotFoundException("帖子不存在")
    post.is_pinned = not post.is_pinned
    await db.commit()
    return {"post_id": str(post_id), "is_pinned": post.is_pinned}


@router.post("/circles/{circle_id}/posts/{post_id}/essence")
async def toggle_essence(
    circle_id: uuid.UUID,
    post_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """加精/取消加精"""
    await _require_circle_admin(db, circle_id, uuid.UUID(current_user.sub))
    post = await db.get(SocialPost, post_id)
    if not post or post.circle_id != circle_id:
        raise NotFoundException("帖子不存在")
    post.is_essence = not post.is_essence
    await db.commit()
    return {"post_id": str(post_id), "is_essence": post.is_essence}


@router.delete("/circles/{circle_id}/posts/{post_id}")
async def delete_circle_post(
    circle_id: uuid.UUID,
    post_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """删除圈子帖子 (软删除)"""
    await _require_circle_admin(db, circle_id, uuid.UUID(current_user.sub))
    post = await db.get(SocialPost, post_id)
    if not post or post.circle_id != circle_id:
        raise NotFoundException("帖子不存在")
    post.is_deleted = True
    await db.commit()
    return {"post_id": str(post_id), "deleted": True}
