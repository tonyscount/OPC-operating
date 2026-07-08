"""
数据库连接与会话管理。

- 异步 SQLAlchemy 2.0 引擎 (惰性初始化，确保在正确的 event loop 上创建)
- 依赖注入: get_db() 提供 AsyncSession
- 租户过滤: before_cursor_execute 事件自动注入 tenant_id
"""

from contextvars import ContextVar
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# ========== 惰性引擎 & 会话工厂 ==========
# 不在模块级别创建引擎，而是在首次访问时惰性初始化。
# 这确保 create_async_engine 在正确的 event loop 上执行
# (例如 pytest-asyncio 的 session-scoped loop)，避免跨 loop 错误。

_engine = None
_session_factory = None


def _init_engine():
    """惰性初始化引擎和会话工厂 (线程安全由 GIL 保证)"""
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            echo=settings.DB_ECHO,
            pool_pre_ping=True,
        )
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        # 注册租户安全网事件监听器
        event.listen(_engine.sync_engine, "before_cursor_execute", tenant_filter_check)
    return _engine


def _reset_engine():
    """重置引擎 (仅在测试中使用，处理 engine.dispose() 后重新初始化)"""
    global _engine, _session_factory
    if _engine is not None:
        _engine = None
        _session_factory = None


def __getattr__(name: str):
    """
    模块级惰性属性访问。
    所有 `from app.core.database import engine` 和
    `from app.core.database import async_session_factory` 都会透明地
    触发惰性初始化，无需修改调用方代码。
    """
    if name == "engine":
        return _init_engine()
    if name == "async_session_factory":
        _init_engine()
        return _session_factory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ========== 租户上下文 (ContextVar 协程安全) ==========
current_tenant_id: ContextVar[str | None] = ContextVar("current_tenant_id", default=None)


def set_tenant_context(tenant_id: str) -> None:
    """设置当前协程的租户上下文"""
    current_tenant_id.set(tenant_id)


def get_tenant_context() -> str | None:
    """获取当前协程的租户上下文"""
    return current_tenant_id.get()


# ========== 依赖注入 ==========
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖: 获取数据库会话，请求结束时自动关闭"""
    # 惰性访问 session_factory，触发首次初始化
    _init_engine()
    async with _session_factory() as session:
        try:
            # 设置 PostgreSQL RLS 租户上下文
            tenant_id = get_tenant_context()
            if tenant_id:
                await session.execute(
                    text("SELECT set_config('app.current_tenant_id', :tid, false)"),
                    {"tid": tenant_id},
                )
            yield session
        finally:
            await session.close()


# ========== 租户自动过滤 (SQLAlchemy 事件层) ==========
# 说明: 这个事件监听器作为"安全网"——即使开发者忘记在查询中写 tenant_id 过滤，
# 它也会在 SQL 执行前检查并记录警告。真正的过滤依赖 RLS + 中间件 + 代码规范三层保障。

TENANT_AWARE_TABLES = {
    # 将在各模块注册时动态填充
    # 格式: "tablename" -> "tenant_id_column"
}


def tenant_filter_check(conn, cursor, statement, parameters, context, executemany):
    """
    安全网: 检查写操作是否可能跨租户。
    注意: 这只是审计日志 + 开发环境告警，实际隔离依赖 RLS + 中间件。
    """
    import re

    if settings.APP_ENV != "development":
        return  # 生产环境仅靠 RLS

    statement_str = str(statement)
    # 简单检测: UPDATE/DELETE 无 WHERE 子句
    if re.match(r"^\s*(UPDATE|DELETE)\s", statement_str, re.IGNORECASE):
        if "where" not in statement_str.lower():
            import logging

            logger = logging.getLogger("tenant.safety_net")
            logger.warning(
                f"Potential tenant-unsafe query detected (no WHERE clause): {statement_str[:200]}"
            )
