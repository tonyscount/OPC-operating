"""
中间件栈 —— 请求处理管道。

1. TenantMiddleware: 从 JWT 提取 tenant_id，注入请求上下文
2. RequestLoggingMiddleware: 请求日志
3. CORSMiddleware: 跨域处理 (在 main.py 中通过内置中间件处理)

全部使用纯 ASGI 中间件，避免 BaseHTTPMiddleware 与 pytest-asyncio/anyio TaskGroup 的兼容问题。
"""

import time
import logging
from uuid import uuid4

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.database import set_tenant_context
from app.core.security import decode_token

logger = logging.getLogger("opc.middleware")


# ========== 租户中间件 ==========
class TenantMiddleware:
    """
    请求入口: 自动从 Authorization Header 解析 JWT，提取 tenant_id，
    注入到 ContextVar 和 request.state。
    此后所有数据库操作自动带租户隔离。
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 生成请求 ID
        request_id = str(uuid4())[:8]

        # 从 headers 提取认证信息
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        tenant_id = None
        user_id = None

        if auth_header.startswith("Bearer "):
            try:
                token = auth_header[len("Bearer "):]
                payload = decode_token(token)
                set_tenant_context(payload.tenant_id)
                tenant_id = payload.tenant_id
                user_id = payload.sub
            except Exception:
                pass

        scope.setdefault("state", type("State", (), {})())
        state = scope["state"]
        state.request_id = request_id
        state.tenant_id = tenant_id
        state.user_id = user_id

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
        state = scope.get("state", {})
        rid = getattr(state, "request_id", "-") if hasattr(state, "request_id") else "-"
        tid = getattr(state, "tenant_id", "-") if hasattr(state, "tenant_id") else "-"

        logger.info(
            f"[{rid}] {scope['method']} {scope['path']} "
            f"| tenant={tid} "
            f"| {status_code} "
            f"| {elapsed:.1f}ms"
        )
