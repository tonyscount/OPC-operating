"""
Prometheus 可观测性 — HTTP / DB / Redis / 业务指标

暴露: GET /metrics (Prometheus 格式)

自定义指标:
  - opc_http_requests_total         HTTP 请求计数
  - opc_http_request_duration_ms    HTTP 请求延迟
  - opc_cache_hits_total            缓存命中
  - opc_cache_misses_total          缓存未命中
  - opc_posts_total                 帖子总数
  - opc_users_online                WebSocket 在线用户
"""

import time
from typing import Callable

from prometheus_client import Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ═══════════════════════════════════════
# HTTP 指标
# ═══════════════════════════════════════

http_requests_total = Counter(
    "opc_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)

http_request_duration = Histogram(
    "opc_http_request_duration_ms",
    "HTTP request duration in milliseconds",
    ["method", "path"],
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
)

# ═══════════════════════════════════════
# 缓存指标
# ═══════════════════════════════════════

cache_hits = Counter(
    "opc_cache_hits_total",
    "Total cache hits",
)

cache_misses = Counter(
    "opc_cache_misses_total",
    "Total cache misses",
)

# ═══════════════════════════════════════
# 业务指标
# ═══════════════════════════════════════

posts_total = Gauge(
    "opc_posts_total",
    "Total posts in the platform",
)

users_online = Gauge(
    "opc_users_online",
    "Currently connected WebSocket users",
)

users_registered = Gauge(
    "opc_users_registered_total",
    "Total registered users",
)

db_connections_active = Gauge(
    "opc_db_connections_active",
    "Active database connections (approximate)",
)

# ═══════════════════════════════════════
# HTTP 中间件 — 自动采集所有请求
# ═══════════════════════════════════════

class MetricsMiddleware(BaseHTTPMiddleware):
    """自动采集每个 HTTP 请求的计数 + 延迟"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 跳过 /metrics 自身
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000

        # 简化 path (避免高基数)
        path = _normalize_path(request.url.path, response.status_code)

        http_requests_total.labels(
            method=request.method,
            path=path,
            status_code=str(response.status_code),
        ).inc()

        http_request_duration.labels(
            method=request.method,
            path=path,
        ).observe(elapsed_ms)

        return response


def _normalize_path(path: str, status_code: int) -> str:
    """将 UUID 替换为 {id} 避免指标爆炸"""
    # 匹配 UUID 模式
    import re
    path = re.sub(
        r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "/{id}", path
    )
    # 匹配数字 ID
    path = re.sub(r"/\d{6,}", "/{id}", path)
    # 404 统一标记
    if status_code == 404:
        path = "/{not_found}"
    return path


# ═══════════════════════════════════════
# /metrics 端点
# ═══════════════════════════════════════

async def metrics_endpoint():
    """返回 Prometheus 格式指标"""
    from prometheus_client import REGISTRY
    return Response(
        content=generate_latest(REGISTRY),
        media_type="text/plain; charset=utf-8",
    )
