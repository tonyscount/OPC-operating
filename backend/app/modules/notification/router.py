"""
通知 & 会话 API

GET    /notifications                   — 我的通知列表
PATCH  /notifications/{id}/read         — 标记已读
POST   /notifications/read-all          — 全部已读
GET    /notifications/unread-count      — 未读数
GET    /conversations                   — 会话列表
GET    /conversations/{id}/messages     — 消息历史
POST   /conversations                   — 创建会话
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select, or_, and_

from app.core.database import get_db
from app.core.security import TokenPayload, get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException
from app.modules.notification.models import (
    Conversation, ConversationParticipant, Message, Notification,
)

router = APIRouter()


# ============================================================
# 通知
# ============================================================

@router.get("/notifications")
async def list_notifications(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """我的通知列表"""
    uid = uuid.UUID(current_user.sub)
    conditions = [Notification.recipient_id == uid, Notification.is_deleted == False]
    if unread_only:
        conditions.append(Notification.is_read == False)

    total = await db.scalar(select(func.count(Notification.id)).where(*conditions))
    notifs = (await db.execute(
        select(Notification).where(*conditions)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    items = [{"id": str(n.id), "title": n.title, "body": n.body,
              "type": n.notification_type, "urgency": n.urgency,
              "is_read": n.is_read, "action_url": n.action_url,
              "created_at": n.created_at.isoformat()} for n in notifs]
    return {"items": items, "total": total or 0, "page": page, "page_size": page_size}


@router.get("/notifications/unread-count")
async def unread_count(
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """未读通知数"""
    uid = uuid.UUID(current_user.sub)
    count = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == uid, Notification.is_read == False,
            Notification.is_deleted == False,
        )
    )
    return {"unread": count or 0}


@router.patch("/notifications/{notif_id}/read")
async def mark_read(
    notif_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """标记单条已读"""
    n = await db.get(Notification, notif_id)
    if n and n.recipient_id == uuid.UUID(current_user.sub):
        n.is_read = True
        await db.commit()
    return {"id": str(notif_id), "read": True}


@router.post("/notifications/read-all")
async def mark_all_read(
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """全部已读"""
    from sqlalchemy import update
    await db.execute(
        update(Notification)
        .where(Notification.recipient_id == uuid.UUID(current_user.sub), Notification.is_read == False)
        .values(is_read=True)
    )
    await db.commit()
    return {"message": "全部已读"}


# ============================================================
# 会话
# ============================================================

@router.get("/conversations")
async def list_conversations(
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """我的会话列表"""
    uid = uuid.UUID(current_user.sub)
    # 查我参与的会话
    result = await db.execute(
        select(Conversation).join(ConversationParticipant).where(
            ConversationParticipant.user_id == uid,
            Conversation.is_deleted == False,
        ).order_by(Conversation.last_message_at.desc())
    )
    convs = result.scalars().all()

    items = []
    for c in convs:
        # 取对方用户信息
        other = (await db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == c.id,
                ConversationParticipant.user_id != uid,
            )
        )).scalar_one_or_none()
        my_participant = (await db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == c.id,
                ConversationParticipant.user_id == uid,
            )
        )).scalar_one_or_none()

        items.append({
            "id": str(c.id), "title": c.title,
            "type": c.conversation_type,
            "last_message": c.last_message,
            "last_message_at": c.last_message_at,
            "unread": my_participant.unread_count if my_participant else 0,
            "other_user_id": str(other.user_id) if other else None,
        })

    return {"items": items}


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    with_user_id: uuid.UUID,
    title: str | None = None,
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """创建/获取私聊会话"""
    uid = uuid.UUID(current_user.sub)
    tid = uuid.UUID(current_user.tenant_id)

    # 检查是否已有 1v1 会话
    existing = (await db.execute(
        select(Conversation).where(
            Conversation.conversation_type == "private",
            Conversation.is_deleted == False,
            Conversation.id.in_(
                select(ConversationParticipant.conversation_id).where(
                    ConversationParticipant.user_id == uid,
                )
            ),
            Conversation.id.in_(
                select(ConversationParticipant.conversation_id).where(
                    ConversationParticipant.user_id == with_user_id,
                )
            ),
        )
    )).scalar_one_or_none()

    if existing:
        return {"id": str(existing.id), "title": existing.title, "existed": True}

    # 新建
    conv = Conversation(tenant_id=tid, conversation_type="private", title=title)
    db.add(conv)
    await db.flush()
    db.add(ConversationParticipant(conversation_id=conv.id, user_id=uid))
    db.add(ConversationParticipant(conversation_id=conv.id, user_id=with_user_id))
    await db.commit()
    return {"id": str(conv.id), "title": title, "existed": False}


@router.get("/conversations/{conv_id}/messages")
async def get_messages(
    conv_id: uuid.UUID,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """会话消息历史"""
    uid = uuid.UUID(current_user.sub)
    # 验证参与者身份
    part = (await db.execute(
        select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conv_id,
            ConversationParticipant.user_id == uid,
        )
    )).scalar_one_or_none()
    if not part:
        raise ForbiddenException("无权访问该会话")

    total = await db.scalar(
        select(func.count(Message.id)).where(Message.conversation_id == conv_id)
    )
    msgs = (await db.execute(
        select(Message).where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    # 标记已读
    part.unread_count = 0
    await db.commit()

    items = [{"id": str(m.id), "sender_id": str(m.sender_id),
              "content": m.content, "type": m.message_type,
              "is_read": m.is_read, "created_at": m.created_at.isoformat()} for m in reversed(msgs)]
    return {"items": items, "total": total or 0, "page": page, "page_size": page_size}


@router.get("/conversations/unread-total")
async def total_unread(
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """所有会话总未读数"""
    uid = uuid.UUID(current_user.sub)
    total = await db.scalar(
        select(func.sum(ConversationParticipant.unread_count)).where(
            ConversationParticipant.user_id == uid,
        )
    )
    return {"unread": total or 0}
