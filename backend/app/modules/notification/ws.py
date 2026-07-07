"""
WebSocket 连接管理器 — 即时通讯 & 实时通知 & 水平扩展

架构:
  L1: 本地连接池 (进程内存 dict)
  L2: Redis Pub/Sub 跨实例消息路由

  发送消息:
    1. 本地连接池查找 → 有则直接推送
    2. Redis publish 到目标用户 channel → 其他实例收到后推送给本地连接
    3. Redis 不可用时降级为纯本地模式

Redis 频道设计:
  ws:msg:{user_id}        — 点对点消息 (私聊/通知)
  ws:presence             — 在线状态广播

用法:
    manager = ConnectionManager()
    await manager.start()       # 启动 Redis 监听
    await manager.connect(uid, ws)
    ...
    await manager.stop()        # 关闭 Redis 监听
"""

import asyncio
import json
import logging
import uuid
from typing import Any

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect

from app.config import settings

logger = logging.getLogger("opc.websocket")

CHANNEL_MSG_PREFIX = "ws:msg:"
CHANNEL_PRESENCE = "ws:presence"


class ConnectionManager:
    """WebSocket 连接池 + Redis Pub/Sub 跨实例路由"""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._listener_task: asyncio.Task | None = None
        self._running = False

    # ================================================================
    # 生命周期
    # ================================================================

    async def start(self) -> None:
        """启动 Redis Pub/Sub 监听 (后台任务)"""
        try:
            self._redis = aioredis.from_url(
                settings.REDIS_URL, db=0,
                protocol=2,  # Redis 3.x compat
                socket_connect_timeout=3,
            )
            await self._redis.ping()
            self._pubsub = self._redis.pubsub()
            # 先订阅 presence 频道
            await self._pubsub.subscribe(CHANNEL_PRESENCE)
            self._running = True
            self._listener_task = asyncio.create_task(self._listen_redis())
            logger.info("WS Redis Pub/Sub started — cross-instance routing enabled")
        except Exception as e:
            logger.warning(f"WS Redis unavailable — local-only mode ({e})")
            self._redis = None
            self._pubsub = None
            self._running = False

    async def stop(self) -> None:
        """关闭 Redis 监听"""
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
        logger.info("WS Redis Pub/Sub stopped")

    # ================================================================
    # 连接管理
    # ================================================================

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """接受连接 + 注册到本地池 + 订阅 Redis channel"""
        await websocket.accept()
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = []
            self._connections[user_id].append(websocket)
        # 更新 Prometheus 指标
        _update_online_metric(len(self._connections))

        # 订阅该用户的 Redis 消息频道
        if self._pubsub and self._running:
            try:
                channel = f"{CHANNEL_MSG_PREFIX}{user_id}"
                await self._pubsub.subscribe(channel)
            except Exception:
                pass

        logger.info(f"WS connected: user={user_id} (local: {len(self._connections[user_id])})")
        await self._broadcast_presence(user_id, "online")

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """断开连接 + 从本地池移除 + 取消 Redis 订阅 (如无其他连接)"""
        async with self._lock:
            if user_id in self._connections:
                self._connections[user_id] = [
                    ws for ws in self._connections[user_id] if ws != websocket
                ]
                still_connected = len(self._connections[user_id]) > 0
                if not still_connected:
                    del self._connections[user_id]

        # 如果没有其他设备连接, 取消 Redis 订阅
        if self._pubsub and self._running and not still_connected:
            try:
                channel = f"{CHANNEL_MSG_PREFIX}{user_id}"
                await self._pubsub.unsubscribe(channel)
            except Exception:
                pass

        logger.info(f"WS disconnected: user={user_id}")
        _update_online_metric(len(self._connections) if still_connected else len(self._connections))
        await self._broadcast_presence(user_id, "offline")

    # ================================================================
    # 消息发送 — L1 本地 + L2 Redis
    # ================================================================

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> bool:
        """
        向指定用户发送消息。

        1. 本地连接 → 直接 WebSocket 推送
        2. Redis Pub/Sub → 广播给其他实例
        返回: True 表示至少发送到一处 (本地或 Redis)
        """
        delivered = False

        # ——— L1: 本地连接 ———
        async with self._lock:
            connections = self._connections.get(user_id, [])

        if connections:
            payload = json.dumps(message, ensure_ascii=False)
            for ws in connections:
                try:
                    await ws.send_text(payload)
                    delivered = True
                except Exception:
                    pass

        # ——— L2: Redis 跨实例 ———
        if self._redis and self._running:
            try:
                msg_data = json.dumps({
                    "target": user_id,
                    "message": message,
                }, ensure_ascii=False)
                channel = f"{CHANNEL_MSG_PREFIX}{user_id}"
                await self._redis.publish(channel, msg_data)
                delivered = True  # 至少发到了 Redis
            except Exception:
                pass

        return delivered

    async def send_to_users(self, user_ids: list[str], message: dict[str, Any]) -> None:
        for uid in user_ids:
            await self.send_to_user(uid, message)

    async def broadcast(self, message: dict[str, Any], exclude: str | None = None) -> None:
        """向所有本地在线用户广播"""
        async with self._lock:
            user_ids = list(self._connections.keys())
        for uid in user_ids:
            if uid != exclude:
                await self.send_to_user(uid, message)

    # ================================================================
    # 在线状态
    # ================================================================

    async def _broadcast_presence(self, user_id: str, status: str) -> None:
        """广播在线状态 (本地 + Redis)"""
        msg = {"type": "presence", "user_id": user_id, "status": status}
        # 本地
        await self.broadcast(msg, exclude=user_id)
        # Redis
        if self._redis and self._running:
            try:
                await self._redis.publish(
                    CHANNEL_PRESENCE,
                    json.dumps(msg, ensure_ascii=False),
                )
            except Exception:
                pass

    # ================================================================
    # 通知推送
    # ================================================================

    async def push_notification(self, recipient_id: str, notification: dict) -> bool:
        return await self.send_to_user(recipient_id, {
            "type": "notification",
            "id": notification.get("id", ""),
            "title": notification.get("title", ""),
            "body": notification.get("body", ""),
            "urgency": notification.get("urgency", "normal"),
            "action_url": notification.get("action_url", ""),
            "created_at": notification.get("created_at", ""),
        })

    # ================================================================
    # 消息持久化
    # ================================================================

    async def persist_message(
        self, conversation_id: str, sender_id: str, content: str, tenant_id: str,
        message_type: str = "text",
    ) -> str:
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
            conv = await db.get(Conversation, uuid.UUID(conversation_id))
            if conv:
                conv.last_message = content[:200]
                conv.last_message_at = msg.created_at
            await db.commit()
            return str(msg.id)

    # ================================================================
    # Redis Pub/Sub 监听器
    # ================================================================

    async def _listen_redis(self) -> None:
        """
        后台任务: 持续监听 Redis Pub/Sub 消息。
        收到消息后推送给本地 WebSocket 连接。
        """
        while self._running and self._pubsub:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message is None:
                    continue
                await self._handle_redis_message(message)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("WS Redis listener error")
                await asyncio.sleep(1)

    async def _handle_redis_message(self, msg: dict) -> None:
        """处理从 Redis 收到的消息"""
        channel = msg.get("channel", "")
        if isinstance(channel, bytes):
            channel = channel.decode()
        data_raw = msg.get("data", "")
        if isinstance(data_raw, bytes):
            data_raw = data_raw.decode()

        if not data_raw:
            return

        try:
            data = json.loads(data_raw)
        except json.JSONDecodeError:
            return

        # Presence 消息
        if channel == CHANNEL_PRESENCE:
            user_id = data.get("user_id", "")
            # 只推送给本地连接 (不广播, 避免循环)
            await self._local_broadcast(data, exclude=user_id)
            return

        # 点对点消息 (ws:msg:{user_id})
        if channel.startswith(CHANNEL_MSG_PREFIX):
            target = data.get("target", "")
            message = data.get("message", {})
            if target and message:
                await self._local_send(target, message)

    async def _local_send(self, user_id: str, message: dict) -> bool:
        """仅推送到本地连接 (不经过 Redis)"""
        async with self._lock:
            connections = self._connections.get(user_id, [])
        if not connections:
            return False
        payload = json.dumps(message, ensure_ascii=False)
        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                pass
        return True

    async def _local_broadcast(self, message: dict, exclude: str | None = None) -> None:
        """仅向本地连接广播"""
        async with self._lock:
            user_ids = list(self._connections.keys())
        for uid in user_ids:
            if uid != exclude:
                await self._local_send(uid, message)

    # ================================================================
    # 工具
    # ================================================================

    def is_online(self, user_id: str) -> bool:
        return user_id in self._connections and len(self._connections[user_id]) > 0

    @property
    def online_count(self) -> int:
        return len(self._connections)


# ========== 全局单例 ==========
manager = ConnectionManager()


def _update_online_metric(count: int):
    try:
        from app.core.metrics import users_online
        users_online.set(count)
    except Exception:
        pass


# ========== WebSocket 端点 ==========
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket 连接处理"""
    await manager.connect(user_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))
                continue

            msg_type = data.get("type", "")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            elif msg_type == "private_message":
                target_uid = data.get("to")
                content = data.get("content", "")
                conversation_id = data.get("conversation_id", "")
                tenant_id = data.get("tenant_id", "")
                if target_uid and conversation_id and tenant_id:
                    msg_id = await manager.persist_message(
                        conversation_id=conversation_id,
                        sender_id=user_id,
                        content=content,
                        tenant_id=tenant_id,
                    )
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
                target_uid = data.get("to")
                if target_uid:
                    await manager.send_to_user(target_uid, {
                        "type": "typing",
                        "from": user_id,
                    })

            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                }))

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
    finally:
        await manager.disconnect(user_id, websocket)
