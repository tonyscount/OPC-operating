"""
设备管理 API

POST   /devices               — 注册设备
GET    /devices               — 我的设备列表
GET    /devices/{id}          — 设备详情
PATCH  /devices/{id}          — 更新设备
PATCH  /devices/{id}/status   — 更新在线状态
DELETE /devices/{id}          — 删除设备
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select

from app.core.database import get_db
from app.core.rate_limit import RATE_DEVICE_REGISTER, RATE_DEVICE_STATUS, limiter
from app.core.security import PermissionChecker, TokenPayload, get_current_user
from app.core.exceptions import NotFoundException
from app.modules.social.device_models import Device

router = APIRouter()
require_write = PermissionChecker("social:write")


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_DEVICE_REGISTER)
async def register_device(
    request: Request,
    name: str, device_type: str = "opc_gateway",
    ip_address: str | None = None, port: int | None = None,
    location: str | None = None, latitude: float | None = None, longitude: float | None = None,
    image_url: str | None = None, specs: dict | None = None, tags: list[str] | None = None,
    _: bool = Depends(require_write),
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """注册设备"""
    device = Device(
        tenant_id=uuid.UUID(current_user.tenant_id), owner_id=uuid.UUID(current_user.sub),
        name=name, device_type=device_type, ip_address=ip_address, port=port,
        location=location, latitude=latitude, longitude=longitude,
        image_url=image_url, specs=specs or {}, tags=tags or [],
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return {"id": str(device.id), "name": device.name, "status": device.status}


@router.get("")
async def list_devices(
    device_type: str | None = None, status: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50),
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """我的设备列表"""
    conditions = [Device.tenant_id == uuid.UUID(current_user.tenant_id), Device.is_deleted == False]
    if device_type: conditions.append(Device.device_type == device_type)
    if status: conditions.append(Device.status == status)

    total = await db.scalar(select(func.count(Device.id)).where(*conditions))
    devices = (await db.execute(
        select(Device).where(*conditions).order_by(Device.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    items = [{"id": str(d.id), "name": d.name, "device_type": d.device_type,
              "ip_address": d.ip_address, "location": d.location, "status": d.status,
              "latitude": d.latitude, "longitude": d.longitude,
              "image_url": d.image_url, "tags": d.tags,
              "last_online_at": d.last_online_at} for d in devices]
    return {"items": items, "total": total or 0, "page": page, "page_size": page_size}


@router.get("/{device_id}")
async def get_device(
    device_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """设备详情"""
    d = await db.get(Device, device_id)
    if not d or d.tenant_id != uuid.UUID(current_user.tenant_id):
        raise NotFoundException("设备不存在")
    return {"id": str(d.id), "name": d.name, "device_type": d.device_type,
            "ip_address": d.ip_address, "port": d.port, "location": d.location,
            "latitude": d.latitude, "longitude": d.longitude, "status": d.status,
            "image_url": d.image_url, "specs": d.specs, "tags": d.tags,
            "view_count": d.view_count, "last_online_at": d.last_online_at,
            "owner_id": str(d.owner_id)}


@router.patch("/{device_id}")
async def update_device(
    device_id: uuid.UUID,
    name: str | None = None, ip_address: str | None = None, location: str | None = None,
    image_url: str | None = None, specs: dict | None = None, tags: list[str] | None = None,
    _: bool = Depends(require_write),
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """更新设备信息"""
    d = await db.get(Device, device_id)
    if not d or d.tenant_id != uuid.UUID(current_user.tenant_id):
        raise NotFoundException("设备不存在")
    for k, v in {"name": name, "ip_address": ip_address, "location": location,
                  "image_url": image_url, "specs": specs, "tags": tags}.items():
        if v is not None: setattr(d, k, v)
    await db.commit()
    return {"id": str(d.id), "name": d.name, "status": d.status}


@router.patch("/{device_id}/status")
async def update_device_status(
    device_id: uuid.UUID, status: str,
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """更新设备在线状态"""
    d = await db.get(Device, device_id)
    if not d or d.tenant_id != uuid.UUID(current_user.tenant_id):
        raise NotFoundException("设备不存在")
    d.status = status
    if status == "online":
        d.last_online_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": str(d.id), "status": d.status}


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: uuid.UUID, _: bool = Depends(require_write),
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """删除设备"""
    d = await db.get(Device, device_id)
    if not d or d.tenant_id != uuid.UUID(current_user.tenant_id):
        raise NotFoundException("设备不存在")
    d.is_deleted = True
    d.deleted_at = datetime.now(timezone.utc)
    await db.commit()
