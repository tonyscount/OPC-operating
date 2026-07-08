"""
用户 API — 个人资料 / 搜索 / 发现
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.database import get_db
from app.core.security import TokenPayload, get_current_user
from app.modules.user import service as user_svc
from app.modules.user.schemas import PasswordChange, ProfileUpdate

router = APIRouter()


# ============================================================
# 个人资料
# ============================================================

@router.get("/profile")
async def get_my_profile(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取我的完整资料"""
    return await user_svc.get_profile(
        db, uuid.UUID(current_user.tenant_id), uuid.UUID(current_user.sub),
    )


@router.get("/profile/{user_id}")
async def get_user_profile(
    user_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """查看其他用户的公开资料"""
    return await user_svc.get_profile(
        db, uuid.UUID(current_user.tenant_id), user_id,
    )


@router.patch("/profile")
async def update_my_profile(
    data: ProfileUpdate,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """编辑个人资料"""
    user = await user_svc.update_profile(
        db, uuid.UUID(current_user.tenant_id), uuid.UUID(current_user.sub),
        **data.model_dump(exclude_none=True),
    )
    return {"message": "资料已更新", "display_name": user.display_name, "email": user.email}


@router.post("/profile/password")
async def change_my_password(
    data: PasswordChange,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """修改密码"""
    await user_svc.change_password(
        db, uuid.UUID(current_user.tenant_id), uuid.UUID(current_user.sub),
        data.old_password, data.new_password,
    )
    return {"message": "密码已修改"}


# ============================================================
# 用户搜索
# ============================================================

@router.get("/search")
async def search_users(
    q: str = Query(min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """搜索用户"""
    items, total = await user_svc.search_users(
        db,
        tenant_id=uuid.UUID(current_user.tenant_id),
        current_user_id=uuid.UUID(current_user.sub),
        keyword=q,
        page=page,
        page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ============================================================
# 信誉 & 在线状态
# ============================================================

@router.get("/{user_id}/reputation")
async def get_reputation(
    user_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取用户信誉分和等级"""
    from app.modules.tenant.models import User
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {
        "user_id": str(user.id),
        "score": user.reputation_score,
        "level": user.level,
        "display_name": user.display_name,
    }


@router.get("/online")
async def online_users(
    current_user: TokenPayload = Depends(get_current_user),
):
    """当前在线用户列表"""
    from app.modules.notification.ws import manager as ws_manager

    online_ids = list(ws_manager._connections.keys())
    return {
        "online_count": len(online_ids),
        "user_ids": online_ids,
    }
