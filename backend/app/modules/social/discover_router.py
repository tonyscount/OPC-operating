"""
发现页 API — LBS 附近的人/设备 + 圈子

GET  /discover/nearby      — 附近的同行和设备 (LBS)
GET  /discover/circles     — 行业圈子
POST /discover/greet       — 打招呼
GET  /discover/feed        — 混合信息流 (动态+设备混排)
GET  /users/{id}/business-card — 工程师名片
"""

import uuid
from math import cos, radians

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, or_

from app.core.database import get_db
from app.core.rate_limit import RATE_SOCIAL_FEED, RATE_SOCIAL_GREET, limiter
from app.core.security import TokenPayload, get_current_user
from app.modules.social.device_models import Device, UserStatus, UserSkill, Greet
from app.modules.social.models import SocialPost
from app.modules.tenant.models import User

router = APIRouter()

# 地球半径 (km)
EARTH_RADIUS = 6371.0


@router.get("/nearby")
async def discover_nearby(
    lat: float, lng: float,
    radius_km: float = Query(10, ge=0.1, le=100),
    discover_type: str = Query("all", pattern="^(all|peers|devices)$"),
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """
    LBS 发现: 附近的人和设备。

    用简单的矩形框过滤 + 精确距离排序。
    """
    tid = uuid.UUID(current_user.tenant_id)
    uid = uuid.UUID(current_user.sub)
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * cos(radians(lat)))

    results = []

    # 附近设备
    if discover_type in ("all", "devices"):
        devices = (await db.execute(
            select(Device).where(
                Device.tenant_id == tid, Device.is_deleted == False,
                Device.owner_id != uid,
                Device.latitude.between(lat - lat_delta, lat + lat_delta),
                Device.longitude.between(lng - lng_delta, lng + lng_delta),
            ).limit(20)
        )).scalars().all()

        for d in devices:
            dist = _haversine(lat, lng, d.latitude or 0, d.longitude or 0)
            if dist <= radius_km:
                results.append({
                    "type": "device", "id": str(d.id), "name": d.name,
                    "device_type": d.device_type, "status": d.status,
                    "distance_km": round(dist, 2), "latitude": d.latitude,
                    "longitude": d.longitude, "image_url": d.image_url,
                    "tags": d.tags,
                })

    # 附近同行
    if discover_type in ("all", "peers"):
        peers = (await db.execute(
            select(User).where(
                User.tenant_id == tid, User.status == "active", User.is_deleted == False,
                User.id != uid,
            ).limit(30)
        )).scalars().all()

        for u in peers:
            # 查技能标签
            skills_result = await db.execute(
                select(UserSkill).where(UserSkill.user_id == u.id)
            )
            skill_names = [s.name for s in skills_result.scalars().all()]

            # 查用户状态
            status_result = await db.execute(
                select(UserStatus).where(UserStatus.user_id == u.id)
            )
            status_row = status_result.scalar_one_or_none()

            results.append({
                "type": "peer", "id": str(u.id), "username": u.username,
                "display_name": u.display_name, "avatar_url": u.avatar_url,
                "skills": skill_names,
                "status_emoji": status_row.emoji if status_row else None,
                "status_text": status_row.text if status_row else None,
                "distance_km": round(_haversine(lat, lng, 0, 0), 1),  # TODO: 用户位置
            })

    # 按距离排序
    results.sort(key=lambda x: x.get("distance_km", 999))
    return {"items": results, "center": {"lat": lat, "lng": lng}, "radius_km": radius_km}


@router.get("/circles")
async def discover_circles(
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """行业圈子 (Mock: 按技能标签分组)"""
    tid = uuid.UUID(current_user.tenant_id)
    skills = (await db.execute(
        select(UserSkill.category, func.count(UserSkill.id).label("cnt"))
        .where(UserSkill.tenant_id == tid, UserSkill.is_deleted == False)
        .group_by(UserSkill.category)
    )).all()

    circles = [
        {"name": "OPC UA 认证", "category": "certification", "member_count": 0, "icon": "certificate"},
        {"name": "PLC 专家圈", "category": "hardware", "member_count": 0, "icon": "chip"},
        {"name": "远程运维联盟", "category": "software", "member_count": 0, "icon": "cloud"},
        {"name": "工业协议开发", "category": "protocol", "member_count": 0, "icon": "code"},
    ]
    for row in skills:
        for c in circles:
            if c["category"] == row.category:
                c["member_count"] = row.cnt

    return {"circles": circles}


@router.post("/greet", status_code=201)
@limiter.limit(RATE_SOCIAL_GREET)
async def greet_user(
    request: Request,
    to_user_id: uuid.UUID, message: str | None = None,
    source: str = "lbs", lat: float | None = None, lng: float | None = None,
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """打招呼"""
    greet = Greet(
        from_user_id=uuid.UUID(current_user.sub), to_user_id=to_user_id,
        tenant_id=uuid.UUID(current_user.tenant_id),
        message=message, source=source, latitude=lat, longitude=lng,
    )
    db.add(greet)
    await db.commit()
    return {"id": str(greet.id), "status": "pending"}


@router.get("/feed")
@limiter.limit(RATE_SOCIAL_FEED)
async def hybrid_feed(
    request: Request,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50),
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """
    首页混合信息流: 运维动态 + 设备资产卡片混排。

    混排规则: 按时间倒序，取最近动态和设备，交替排列。
    """
    tid = uuid.UUID(current_user.tenant_id)

    # 最近动态
    posts = (await db.execute(
        select(SocialPost).where(
            SocialPost.tenant_id == tid, SocialPost.is_deleted == False,
            SocialPost.visibility == "public",
        ).order_by(SocialPost.created_at.desc()).limit(page_size)
    )).scalars().all()

    # 在线设备
    devices = (await db.execute(
        select(Device).where(
            Device.tenant_id == tid, Device.is_deleted == False,
        ).order_by(Device.created_at.desc()).limit(page_size)
    )).scalars().all()

    # 交替混排
    items = []
    max_len = max(len(posts), len(devices))
    for i in range(max_len):
        if i < len(posts):
            p = posts[i]
            items.append({"type": "post", "id": str(p.id), "content": p.content[:200],
                          "author_id": str(p.author_id), "like_count": p.like_count,
                          "comment_count": p.comment_count, "created_at": p.created_at.isoformat()})
        if i < len(devices):
            d = devices[i]
            items.append({"type": "device", "id": str(d.id), "name": d.name,
                          "device_type": d.device_type, "status": d.status,
                          "ip_address": d.ip_address, "image_url": d.image_url,
                          "location": d.location, "owner_id": str(d.owner_id)})

    start = (page - 1) * page_size
    return {"items": items[start:start + page_size], "page": page, "page_size": page_size}


@router.get("/users/{user_id}/business-card")
async def business_card(
    user_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """
    工程师名片页: 个人资料 + 技能标签 + 设备列表 + 最新状态。
    """
    user = await db.get(User, user_id)
    if not user:
        return {"error": "用户不存在"}

    # 技能
    skills = (await db.execute(
        select(UserSkill).where(UserSkill.user_id == user_id, UserSkill.is_deleted == False)
    )).scalars().all()

    # 设备
    devices = (await db.execute(
        select(Device).where(
            Device.owner_id == user_id, Device.is_deleted == False,
        ).order_by(Device.status.desc(), Device.created_at.desc()).limit(10)
    )).scalars().all()

    # 当前状态
    status_row = (await db.execute(
        select(UserStatus).where(UserStatus.user_id == user_id)
    )).scalar_one_or_none()

    # 社交统计
    from app.modules.social.models import UserFollow
    follower_count = await db.scalar(
        select(func.count(UserFollow.id)).where(
            UserFollow.following_id == user_id, UserFollow.is_deleted == False,
        )
    )
    following_count = await db.scalar(
        select(func.count(UserFollow.id)).where(
            UserFollow.follower_id == user_id, UserFollow.is_deleted == False,
        )
    )
    device_count = await db.scalar(
        select(func.count(Device.id)).where(
            Device.owner_id == user_id, Device.is_deleted == False,
        )
    )

    return {
        "user": {"id": str(user.id), "username": user.username,
                 "display_name": user.display_name, "avatar_url": user.avatar_url,
                 "email": user.email},
        "status": {"emoji": status_row.emoji, "text": status_row.text} if status_row else None,
        "skills": [{"name": s.name, "category": s.category, "level": s.level,
                     "endorsed_count": s.endorsed_count} for s in skills],
        "devices": [{"id": str(d.id), "name": d.name, "device_type": d.device_type,
                      "status": d.status, "ip_address": d.ip_address,
                      "image_url": d.image_url, "location": d.location} for d in devices],
        "stats": {"followers": follower_count or 0, "following": following_count or 0,
                  "devices": device_count or 0},
    }


# ========== 用户状态 API ==========

@router.get("/users/me/status")
async def get_my_status(
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """获取我的当前状态"""
    status_row = (await db.execute(
        select(UserStatus).where(UserStatus.user_id == uuid.UUID(current_user.sub))
    )).scalar_one_or_none()
    if not status_row:
        return {"emoji": None, "text": None}
    return {"emoji": status_row.emoji, "text": status_row.text, "background_url": status_row.background_url}


@router.patch("/users/me/status")
async def set_my_status(
    emoji: str | None = None, text: str | None = None, background_url: str | None = None,
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """设置我的状态 (24h 后自动过期)"""
    from datetime import datetime, timedelta, timezone
    uid = uuid.UUID(current_user.sub)
    tid = uuid.UUID(current_user.tenant_id)

    row = (await db.execute(
        select(UserStatus).where(UserStatus.user_id == uid)
    )).scalar_one_or_none()

    expires = datetime.now(timezone.utc) + timedelta(hours=24)
    if row:
        row.emoji = emoji
        row.text = text or row.text
        row.background_url = background_url
        row.expires_at = expires
    else:
        row = UserStatus(user_id=uid, tenant_id=tid, emoji=emoji, text=text or "",
                         background_url=background_url, expires_at=expires)
        db.add(row)

    await db.commit()
    return {"emoji": row.emoji, "text": row.text, "expires_at": row.expires_at}


# ========== 技能标签 API ==========

@router.post("/users/me/skills", status_code=201)
async def add_skill(
    name: str, category: str | None = None, level: str = "intermediate",
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """添加技能标签"""
    skill = UserSkill(
        tenant_id=uuid.UUID(current_user.tenant_id), user_id=uuid.UUID(current_user.sub),
        name=name, category=category, level=level,
    )
    db.add(skill)
    await db.commit()
    return {"id": str(skill.id), "name": skill.name}


@router.delete("/users/me/skills/{skill_id}", status_code=204)
async def remove_skill(
    skill_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """删除技能标签"""
    skill = await db.get(UserSkill, skill_id)
    if skill and skill.user_id == uuid.UUID(current_user.sub):
        skill.is_deleted = True
        await db.commit()


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """计算两点间距离 (km)"""
    from math import asin, cos, radians, sin, sqrt
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return EARTH_RADIUS * 2 * asin(sqrt(a))
