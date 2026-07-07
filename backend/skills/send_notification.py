"""
Skill: 发送通知

Agent 调用此 Skill 向指定用户发送站内通知。
实现: 写入 notifications 表 + 通过 WebSocket 实时推送。
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from app.modules.skill.registry import skill_registry

logger = logging.getLogger("opc.skill.notification")


@skill_registry.register(
    name="send_notification",
    display_name="发送通知",
    description="向一个或多个用户发送站内通知消息，写入数据库并实时推送",
    parameters_schema={
        "to_user_ids": {
            "type": "array",
            "description": "接收通知的用户 ID 列表",
            "required": True,
        },
        "title": {
            "type": "string", "description": "通知标题", "required": True,
        },
        "body": {
            "type": "string", "description": "通知正文内容", "required": True,
        },
        "urgency": {
            "type": "string", "description": "紧急程度",
            "enum": ["low", "normal", "high"], "default": "normal",
        },
        "action_url": {
            "type": "string", "description": "点击跳转链接", "required": False,
        },
    },
    timeout=15,
    required_permissions=["notification:send"],
    is_builtin=True,
)
async def send_notification(params: dict, context: dict) -> dict:
    """
    发送站内通知: 写 DB + WS 推送

    context: { user_id, tenant_id, trace_id }
    """
    to_user_ids = params.get("to_user_ids", [])
    title = params.get("title", "")
    body = params.get("body", "")
    urgency = params.get("urgency", "normal")
    action_url = params.get("action_url")
    tenant_id = context.get("tenant_id")
    sender_id = context.get("user_id")

    if not to_user_ids:
        return {"error": "to_user_ids 不能为空", "sent_to": 0}

    from app.core.database import async_session_factory
    from app.modules.notification.models import Notification
    from app.modules.notification.ws import manager as ws_manager

    delivered = 0
    failed = 0
    notification_ids = []

    async with async_session_factory() as db:
        for uid in to_user_ids:
            try:
                # 1. 写入数据库
                notification = Notification(
                    tenant_id=UUID(tenant_id),
                    recipient_id=UUID(uid),
                    sender_id=UUID(sender_id) if sender_id else None,
                    title=title,
                    body=body,
                    notification_type="system",
                    urgency=urgency,
                    action_url=action_url,
                )
                db.add(notification)
                await db.flush()
                nid = str(notification.id)
                notification_ids.append(nid)

                # 2. 通过 WebSocket 实时推送给在线用户
                pushed = await ws_manager.push_notification(uid, {
                    "id": nid,
                    "title": title,
                    "body": body,
                    "urgency": urgency,
                    "action_url": action_url or "",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                if pushed:
                    delivered += 1

            except Exception as e:
                logger.error(f"Failed to send notification to {uid}: {e}")
                failed += 1

        await db.commit()

    logger.info(
        f"[{context.get('trace_id')}] Notification '{title}' → "
        f"{delivered} delivered (WS), {len(to_user_ids)} persisted, {failed} failed"
    )

    return {
        "sent_to": len(to_user_ids),
        "delivered_ws": delivered,
        "persisted": len(notification_ids),
        "failed": failed,
        "notification_ids": notification_ids,
        "title": title,
        "urgency": urgency,
    }
