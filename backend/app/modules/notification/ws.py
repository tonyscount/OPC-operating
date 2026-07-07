"""
WebSocket 连接管理器 — 即时通讯 & 实时通知。

设计:
  - 每个连接对应一个用户 (user_id)
  - 同一用户可多端连接
  - JWT 认证在连接建立时完成
  - 消息持久化到 messages 表
  - 支持: 私聊消息推送、通知推送、在线状态
"""

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("opc.websocket")


class ConnectionManager:
    """
    WebSocket 连接池管理器。

    用法:
        manager = ConnectionManager()

        @router.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket, token: str):
            await manager.connect(user_id, websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    ...
            finally:
                await manager.disconnect(user_id, websocket)
    """

    def __init__(self):
        # user_id -> list[WebSocket]
        self._connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """接受 WebSocket 连接，注册到连接池"""
        await websocket.accept()
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = []
            self._connections[user_id].append(websocket)
        logger.info(f"WS connected: user={user_id} (total connections: {len(self._connections[user_id])})")

        # 通知上线
        await self.broadcast_status(user_id, "online")

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """断开连接，从连接池移除"""
        async with self._lock:
            if user_id in self._connections:
                self._connections[user_id] = [
                    ws for ws in self._connections[user_id] if ws != websocket
                ]
                if not self._connections[user_id]:
                    del self._connections[user_id]
        logger.info(f"WS disconnected: user={user_id}")

        # 通知离线
        await self.broadcast_status(user_id, "offline")

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> bool:
        """向指定用户的所有连接发送消息"""
        async with self._lock:
            connections = self._connections.get(user_id, [])

        if not connections:
            return False

        payload = json.dumps(message, ensure_ascii=False)
        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                # 连接可能已断开但未清理
                pass
        return True

    async def send_to_users(self, user_ids: list[str], message: dict[str, Any]) -> None:
        """向多个用户发送消息"""
        for uid in user_ids:
            await self.send_to_user(uid, message)

    async def broadcast(self, message: dict[str, Any], exclude: str | None = None) -> None:
        """向所有在线用户广播消息"""
        async with self._lock:
            user_ids = list(self._connections.keys())

        for uid in user_ids:
            if uid != exclude:
                await self.send_to_user(uid, message)

    async def broadcast_status(self, user_id: str, status: str) -> None:
        await self.broadcast({
            "type": "presence", "user_id": user_id, "status": status,
        })

    async def push_notification(self, recipient_id: str, notification: dict) -> bool:
        """推送通知到指定用户 (用于 send_notification Skill)"""
        return await self.send_to_user(recipient_id, {
            "type": "notification",
            "id": notification.get("id", ""),
            "title": notification.get("title", ""),
            "body": notification.get("body", ""),
            "urgency": notification.get("urgency", "normal"),
            "action_url": notification.get("action_url", ""),
            "created_at": notification.get("created_at", ""),
        })

    async def persist_message(
        self, conversation_id: str, sender_id: str, content: str, tenant_id: str,
        message_type: str = "text",
    ) -> str:
        """持久化消息到数据库"""
        from app.core.database import async_session_factory
        from app.modules.notification.models import Message, Conversation

        async with async_session_factory() as db:
            msg = Message(
                tenant_id=uuid.UUID(tenant_id),
                conversation_id=uuid.UUID(conversation_id),
                sender_id=uuid.UUID(sender_id),
                content=content,
                message_type=message_type,
            )
            db.add(msg)

            # 更新会话最后消息
            conv = await db.get(Conversation, uuid.UUID(conversation_id))
            if conv:
                conv.last_message = content[:200]
                conv.last_message_at = msg.created_at

            await db.commit()
            return str(msg.id)

    def is_online(self, user_id: str) -> bool:
        return user_id in self._connections and len(self._connections[user_id]) > 0

    @property
    def online_count(self) -> int:
        return len(self._connections)


# ========== 全局单例 ==========
manager = ConnectionManager()


# ========== WebSocket 端点 ==========
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket 连接处理。

    前端连接方式:
        const ws = new WebSocket(`ws://localhost:8000/ws?token=${jwt_token}`);
    """
    await manager.connect(user_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "无效的 JSON"}))
                continue

            msg_type = data.get("type", "")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            elif msg_type == "private_message":
                # 私聊消息 — 持久化 + 实时推送
                target_uid = data.get("to")
                content = data.get("content", "")
                conversation_id = data.get("conversation_id", "")
                tenant_id = data.get("tenant_id", "")
                if target_uid and conversation_id and tenant_id:
                    # 1. 持久化到 DB
                    msg_id = await manager.persist_message(
                        conversation_id=conversation_id,
                        sender_id=user_id,
                        content=content,
                        tenant_id=tenant_id,
                    )
                    # 2. 实时推送到接收方
                    delivered = await manager.send_to_user(target_uid, {
                        "type": "private_message",
                        "id": msg_id,
                        "conversation_id": conversation_id,
                        "from": user_id,
                        "content": content,
                        "timestamp": data.get("timestamp", ""),
                    })
                    await websocket.send_text(json.dumps({
                        "type": "ack",
                        "message_id": msg_id,
                        "delivered": delivered,
                    }))

            elif msg_type == "typing":
                # 正在输入
                target_uid = data.get("to")
                if target_uid:
                    await manager.send_to_user(target_uid, {
                        "type": "typing",
                        "from": user_id,
                    })

            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"未知消息类型: {msg_type}",
                }))

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
    finally:
        await manager.disconnect(user_id, websocket)
