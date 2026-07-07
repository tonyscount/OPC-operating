"""
限流模块 — Redis-backed 滑动窗口限流

架构:
  - 基于 slowapi + Redis 存储 (多实例共享计数器)
  - 双层 key: 用户 ID (已认证) / IP (未认证)
  - 分级限流: auth / social_write / social_read / search / global

X-RateLimit-* 响应头 (slowapi 自动注入):
  - X-RateLimit-Limit      当前窗口最大请求数
  - X-RateLimit-Remaining  剩余可用次数
  - X-RateLimit-Reset      窗口重置时间 (epoch seconds)
  - Retry-After            被限流时建议重试秒数

用法:
    from app.core.rate_limit import limiter

    @router.post("/login")
    @limiter.limit("10/minute")          # 端点级覆盖
    async def login(request: Request, ...):
        ...

    # 或者在 router 级别: 无需装饰器, 走 default_limits
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings


# ============================================================
# Key 函数 — 识别请求主体
# ============================================================

def get_user_or_ip_key(request) -> str:
    """
    返回限流 key: 已认证用户用 user:<uuid>, 否则用 ip:<addr>。

    依赖 TenantMiddleware 先解析 JWT 并注入 request.state.user_id。
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


# ============================================================
# 构建 Redis 存储 URI (为 rate limit 使用独立 DB编号)
# ============================================================

def _build_redis_storage_uri() -> str:
    """
    从 settings.REDIS_URL 构造 limits 库可用的 Redis URI。

    REDIS_URL 格式: redis://[:password@]host:port[/db]
    rate limit 使用 DB 1, 独立于 Celery(DB 0)、缓存(DB 2 预留)。
    """
    url = settings.REDIS_URL
    # 去掉已有的 /db 后缀, 追加 /1
    if "/" in url.rsplit(":", 1)[-1] or url.count("/") > 2:
        # 格式: redis://host:port/db → 替换 /db
        parts = url.rsplit("/", 1)
        url = parts[0]
    return f"{url}/1"


# ============================================================
# 限流器单例
# ============================================================

limiter = Limiter(
    key_func=get_user_or_ip_key,
    storage_uri=_build_redis_storage_uri(),
    default_limits=["200/minute"],     # 全局兜底: 所有未装饰端点
    headers_enabled=True,              # 自动注入 X-RateLimit-* 头
    swallow_errors=True,               # Redis 挂了不让业务中断
)


# ============================================================
# 限流配额 — 按模块分级
# ============================================================

# ——— 认证 (防暴力破解) ———
RATE_AUTH_LOGIN    = "10/minute"    # 登录: 每用户/IP 每分钟 10 次
RATE_AUTH_REGISTER = "5/hour"       # 注册: 每 IP 每小时 5 次
RATE_AUTH_REFRESH  = "30/minute"    # Token 刷新

# ——— 社交 写操作 (防刷) ———
RATE_SOCIAL_CREATE_POST   = "20/minute"   # 发帖
RATE_SOCIAL_COMMENT       = "30/minute"   # 评论/回复
RATE_SOCIAL_LIKE          = "60/minute"   # 点赞/取消 (toggle 高并发)
RATE_SOCIAL_FOLLOW        = "30/minute"   # 关注/取关
RATE_SOCIAL_FRIEND_REQUEST = "20/minute"  # 好友申请
RATE_SOCIAL_GREET          = "15/minute"  # 打招呼

# ——— 社交 读操作 ———
RATE_SOCIAL_FEED   = "120/minute"   # 动态流
RATE_SOCIAL_SEARCH = "30/minute"    # 搜索

# ——— 设备 ———
RATE_DEVICE_REGISTER = "10/minute"  # 注册设备
RATE_DEVICE_STATUS   = "30/minute"  # 状态更新 (心跳)

# ——— Agent / AI ———
RATE_AGENT_RUN = "20/minute"        # 执行智能体 (成本敏感)

# ——— 知识库 ———
RATE_KNOWLEDGE_UPLOAD   = "30/minute"
RATE_KNOWLEDGE_ASK       = "20/minute"   # RAG 问答 (LLM 成本)

# ——— OA ———
RATE_OA_APPLY    = "10/minute"      # 提交审批
RATE_OA_APPROVE  = "30/minute"      # 审批操作
