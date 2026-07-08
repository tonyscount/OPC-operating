"""
中间件栈 —— 请求处理管道。

全部使用纯 ASGI 中间件，避免 BaseHTTPMiddleware 与 pytest-asyncio/anyio TaskGroup 的兼容问题。

注意: scope["state"] 由 Starlette Request 构造函数初始化，
ASGI 中间件不应直接操作它；租户上下文通过 ContextVar 传递。
"""

import time
import logging

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.database import set_tenant_context
from app.core.security import decode_token

logger = logging.getLogger("opc.middleware")


# ========== 租户中间件 ==========
class TenantMiddleware:
    """
    从 Authorization Header 解析 JWT，将 tenant_id 注入 ContextVar。
    不做 scope["state"] 操作，避免干扰 Starlette State 对象。
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()

        if auth_header.startswith("Bearer "):
            try:
                token = auth_header[len("Bearer "):]
                payload = decode_token(token)
                set_tenant_context(payload.tenant_id)
            except Exception:
                pass

        await self.app(scope, receive, send)


# ========== 请求日志中间件 ==========
class RequestLoggingMiddleware:
    """记录每个请求的方法、路径、耗时、状态码"""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            f"{scope['method']} {scope['path']} "
            f"| {status_code} "
            f"| {elapsed:.1f}ms"
        )
