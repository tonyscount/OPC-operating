"""
中间件栈 —— 请求处理管道。

1. TenantMiddleware: 从 JWT 提取 tenant_id，注入请求上下文
2. RequestLoggingMiddleware: 请求日志
3. CORSMiddleware: 跨域处理 (在 main.py 中通过内置中间件处理)
"""

import time
import logging
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.database import set_tenant_context
from app.core.security import decode_token

logger = logging.getLogger("opc.middleware")


# ========== 租户中间件 ==========
class TenantMiddleware(BaseHTTPMiddleware):
    """
    请求入口: 自动从 Authorization Header 解析 JWT，提取 tenant_id，
    注入到 ContextVar 和 request.state。

    此后所有数据库操作自动带租户隔离。
    """

    async def dispatch(self, request: Request, call_next):
        # 生成请求 ID
        request_id = str(uuid4())[:8]
        request.state.request_id = request_id

        # 尝试从 Authorization Header 提取租户信息
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                token = auth_header[len("Bearer "):]
                payload = decode_token(token)
                set_tenant_context(payload.tenant_id)
                request.state.tenant_id = payload.tenant_id
                request.state.user_id = payload.sub
                request.state.org_id = payload.org_id
                request.state.roles = payload.roles
            except Exception:
                # Token 无效时静默处理，让业务层的 get_current_user 决定是否拒绝
                pass

        # 对于跨租户操作的特殊 Header
        cross_tenant = request.headers.get("X-Cross-Tenant", "false")
        if cross_tenant.lower() == "true":
            request.state.cross_tenant = True
            # 跨租户操作需要超级管理员权限，在业务层校验

        # 初始化速率限制状态 (兼容 slowapi 0.1.x + Starlette 0.41+)
        try:
            _ = request.state.view_rate_limit
        except AttributeError:
            request.state._state["view_rate_limit"] = None

        response = await call_next(request)

        # 响应头附加请求 ID，方便前端排查
        response.headers["X-Request-ID"] = request_id
        return response


# ========== 请求日志中间件 ==========
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """记录每个请求的方法、路径、耗时、状态码"""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()

        response = await call_next(request)

        elapsed = (time.perf_counter() - start) * 1000  # ms
        rid = getattr(request.state, "request_id", "-")
        tid = getattr(request.state, "tenant_id", "-")

        logger.info(
            f"[{rid}] {request.method} {request.url.path} "
            f"| tenant={tid} "
            f"| {response.status_code} "
            f"| {elapsed:.1f}ms"
        )

        response.headers["X-Elapsed-Ms"] = f"{elapsed:.1f}"
        return response
