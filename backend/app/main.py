"""
OPC Platform — FastAPI 应用入口

启动:
    uvicorn app.main:app --reload
    docker compose up api
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.core.rate_limit import limiter

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.metrics import MetricsMiddleware, metrics_endpoint
from app.core.middleware import RequestLoggingMiddleware, TenantMiddleware


# ========== 应用生命周期 ==========
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """启动 & 关闭钩子"""
    # 最先初始化日志系统
    from app.core.logging_config import setup_logging
    setup_logging()
    from app.core.settings_manager import manager as settings_mgr
    settings_mgr.load_from_env()

    import logging
    logger = logging.getLogger("opc")

    # 关键配置校验
    config_warnings = settings.validate_critical()
    for w in config_warnings:
        if w.startswith("CRITICAL"):
            logger.critical(w)
        else:
            logger.warning(w)

    logger.info(f"[START] {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    logger.info(f"   Environment: {settings.APP_ENV}")
    logger.info(f"   LLM Provider: {settings.LLM_PROVIDER}")

    # 启动时: 自动发现并注册 Skills
    from app.modules.skill.registry import skill_registry
    await skill_registry.auto_discover(settings.SKILLS_DIR)
    # 导入子目录 Skill 包 (pkgutil 不扫子目录)
    try: import skills.web_search  # noqa: F401
    except Exception as e: logger.warning(f"web_search: {e}")
    try: import skills.data_query  # noqa: F401
    except Exception as e: logger.warning(f"data_query: {e}")
    try: import skills.event_planner  # noqa: F401
    except Exception as e: logger.warning(f"event_planner: {e}")
    try: import skills.daily_briefing  # noqa: F401
    except Exception as e: logger.warning(f"daily_briefing: {e}")
    try: import skills.send_notification  # noqa: F401
    except Exception as e: logger.warning(f"send_notification: {e}")
    try: import skills.read_user_profile  # noqa: F401
    except Exception as e: logger.warning(f"read_user_profile: {e}")
    try: import skills.ppt_master  # noqa: F401
    except Exception as e: logger.warning(f"ppt_master: {e}")
    logger.info(f"   Skills loaded: {skill_registry.count}")

    # 启动 WebSocket Redis Pub/Sub (跨实例消息路由)
    from app.modules.notification.ws import manager as ws_manager
    await ws_manager.start()

    # 加载 Lenny Skills (Product Management 知识库)
    try:
        from skills.lenny_loader import load_lenny_skills
        lenny_count = await load_lenny_skills()
        logger.info(f"   Lenny Skills loaded: {lenny_count}")
    except Exception as e:
        logger.warning(f"   Lenny Skills not loaded: {e}")

    yield

    # 关闭时: 清理资源
    from app.modules.notification.ws import manager as ws_manager
    await ws_manager.stop()
    from app.core.database import engine
    await engine.dispose()
    logger.info("OPC Platform shut down")




# ========== 应用工厂 ==========
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ---- CORS ----
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- 租户中间件 (最先执行) ----
    app.add_middleware(TenantMiddleware)

    # ---- 可观测性 (最外层, 采集所有请求) ----
    app.add_middleware(MetricsMiddleware)

    # ---- 请求日志 ----
    app.add_middleware(RequestLoggingMiddleware)

    # ---- 限流 ----
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ---- 异常处理器 ----
    register_exception_handlers(app)

    # ---- 注册路由 ----
    register_routers(app)

    # ---- 健康检查 ----
    @app.get("/health")
    async def health():
        return {"status": "ok", "version": settings.APP_VERSION}

    # ---- Prometheus 指标 ----
    @app.get("/metrics")
    async def metrics():
        return await metrics_endpoint()

    # ---- 前端静态文件 (生产模式) ----
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    dist_path = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
    if dist_path.exists():
        app.mount("/assets", StaticFiles(directory=dist_path / "assets"), name="assets")
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            """SPA fallback: 非 API 路由返回 index.html"""
            file_path = dist_path / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(dist_path / "index.html")

    return app


# ========== 路由注册 ==========
def register_routers(app: FastAPI) -> None:
    from app.modules.tenant.router import router as tenant_router
    from app.modules.auth.router import router as auth_router
    from app.modules.social.router import router as social_router
    from app.modules.user.router import router as user_router
    from app.modules.schedule.router import router as schedule_router

    # 认证相关 (无需租户上下文)
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["认证"])

    # 用户 Profile (社交基础)
    app.include_router(user_router, prefix="/api/v1/users", tags=["用户"])

    # 租户管理
    app.include_router(tenant_router, prefix="/api/v1/tenant", tags=["租户"])

    # 社交
    app.include_router(social_router, prefix="/api/v1/social", tags=["社交"])

    # 定时任务管理
    app.include_router(schedule_router, prefix="/api/v1/schedule", tags=["定时任务"])

    # 知识库 (RAG)
    from app.modules.knowledge.router import router as knowledge_router
    app.include_router(knowledge_router, prefix="/api/v1/knowledge", tags=["知识库"])

    # 搜索
    from app.modules.search.router import router as search_router
    app.include_router(search_router, prefix="/api/v1/search", tags=["搜索"])

    # Skill 系统
    from app.modules.skill.router import router as skill_router
    app.include_router(skill_router, prefix="/api/v1/skills", tags=["Skills"])

    # 多智能体
    from app.modules.agent.router import router as agent_router
    app.include_router(agent_router, prefix="/api/v1/agent", tags=["Agent"])

    # OA 审批工作流
    from app.modules.social.oa_router import router as oa_router
    app.include_router(oa_router, prefix="/api/v1/oa", tags=["OA审批"])

    # 交易
    from app.modules.trade.router import router as trade_router
    app.include_router(trade_router, prefix="/api/v1/trade", tags=["交易"])

    # 运营后台
    from app.modules.social.ops_router import router as ops_router
    app.include_router(ops_router, prefix="/api/v1/ops", tags=["运营"])

    # 设备管理
    from app.modules.social.device_router import router as device_router
    app.include_router(device_router, prefix="/api/v1/devices", tags=["设备"])

    # 发现页 (LBS + 混合信息流 + 名片 + 状态 + 技能)
    from app.modules.social.discover_router import router as discover_router
    app.include_router(discover_router, prefix="/api/v1/discover", tags=["发现"])

    # LLM 设置
    from app.modules.auth.settings_router import router as settings_router
    app.include_router(settings_router, prefix="/api/v1/settings", tags=["设置"])

    # 通知 & 会话
    from app.modules.notification.router import router as notification_router
    app.include_router(notification_router, prefix="/api/v1", tags=["通知&会话"])

    # WebSocket (即时通讯)
    from app.modules.notification.ws import websocket_endpoint
    from app.core.security import decode_token
    from fastapi import WebSocket, WebSocketDisconnect, Query

    @app.websocket("/ws")
    async def ws_connect(websocket: WebSocket, token: str = Query(...)):
        """WebSocket 连接入口 — 通过 query param 传递 JWT token"""
        try:
            payload = decode_token(token)
            user_id = payload.sub
        except Exception:
            await websocket.close(code=4001, reason="认证失败")
            return
        await websocket_endpoint(websocket, user_id)

    # Phase 0-8 模块全部注册完成 ✅


# ========== 应用实例 ==========
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
