"""
多智能体 API

POST   /agent/run              — 执行 Agent (支持 single/sequential/router/debate)
GET    /agent/list             — Agent 列表
POST   /agent/register         — 注册 Agent (代码)
GET    /agent/executions       — 执行历史
GET    /agent/executions/{id}  — 执行详情
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.database import get_db
from app.core.rate_limit import RATE_AGENT_RUN, limiter
from app.core.security import PermissionChecker, TokenPayload, get_current_user
from app.modules.agent.orchestrator import AgentDefinition, orchestrator
from app.modules.agent.schemas import AgentCreate, AgentExecutionRequest, AgentExecutionResponse, AgentResponse, AgentUpdate, AuditRequest

router = APIRouter()
require_agent_exec = PermissionChecker("agent:execute")
require_agent_mgmt = PermissionChecker("agent:manage")

# 注册 3 个内置 Agent
_builtin_registered = False


def _register_builtin_agents():
    global _builtin_registered
    if _builtin_registered:
        return
    _builtin_registered = True

    # 分析师 Agent
    orchestrator.register_agent(AgentDefinition(
        name="analyst",
        role_prompt="""你是 OPC 社群运营助手。你可以自主选择合适的工具完成任务。

你的核心能力:
1. 使用 data_query 查询社群数据（成员数、活跃度、热门帖子）
2. 使用 event_planner 基于真实数据生成活动策划方案
3. 使用 search_knowledge 在知识库中查找历史复盘和经验
4. 使用 web_search 搜索外部最新资讯（仅在知识库无法回答时）
5. 使用 read_user_profile 查看用户信息

工作方式:
- 当用户询问社群数据 → 先调 data_query 获取真实数据
- 当用户要策划活动 → 先调 data_query 了解社群现状 → 再调 event_planner 生成方案
- 当用户问经验/历史 → 先调 search_knowledge 查知识库
- 将多个工具的结果综合后，用中文给出结构化的回答""",
        tools=["data_query", "event_planner", "search_knowledge", "web_search", "read_user_profile"],
        max_iterations=15,
    ))

    # 客服 Agent
    orchestrator.register_agent(AgentDefinition(
        name="support_agent",
        role_prompt="""你是一个客服助手 Agent。你的职责是:
1. 回答用户关于 OPC 平台使用的问题
2. 在知识库中搜索相关帮助文档
3. 对于无法解决的问题，引导用户联系人工客服
4. 保持友好、耐心的态度，使用中文回复""",
        tools=["search_knowledge"],
        max_iterations=8,
    ))

    # 审核 Agent
    orchestrator.register_agent(AgentDefinition(
        name="reviewer",
        role_prompt="""你是一个内容审核 Agent。你的职责是:
1. 审查用户提交的内容是否符合社区规范
2. 检查是否有敏感信息、违规内容
3. 给出审核意见: 通过/拒绝/需要修改
4. 客观公正，使用中文回复""",
        tools=["read_user_profile"],
        max_iterations=5,
    ))

    # 综合 Agent (用于 Debate 模式的裁判)
    orchestrator.register_agent(AgentDefinition(
        name="judge",
        role_prompt="""你是一个综合评审 Agent。你的职责是:
1. 综合多个 Agent 的分析意见
2. 找出各方观点的共识和分歧
3. 给出最终的、平衡的结论
4. 用中文回复，明确标注结论来源""",
        tools=["search_knowledge"],
        max_iterations=5,
    ))


_register_builtin_agents()


# ============================================================
# Agent 管理
# ============================================================

@router.get("/metrics")
async def agent_metrics(
    current_user: TokenPayload = Depends(get_current_user),
):
    """AI 可观测性: token 消耗、调用次数、成本"""
    from app.core.ai_metrics import metrics as ai_metrics
    return {
        "session": ai_metrics.get_session_stats(),
        "recent_calls": ai_metrics.get_recent_calls(10),
    }


@router.get("/list")
async def list_agents(
    current_user: TokenPayload = Depends(get_current_user),
):
    """获取所有可用 Agent"""
    return {"agents": orchestrator.list_agents()}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_agent(
    data: AgentCreate,
    _: bool = Depends(require_agent_mgmt),
    current_user: TokenPayload = Depends(get_current_user),
):
    """注册自定义 Agent"""
    agent = AgentDefinition(
        name=data.name,
        role_prompt=data.role_prompt,
        tools=data.tools,
        knowledge_base_ids=data.knowledge_base_ids,
        model=data.model,
        temperature=data.temperature,
        max_iterations=data.max_iterations,
    )
    orchestrator.register_agent(agent)
    return {"name": agent.name, "tools": agent.tools}


# ============================================================
# Agent 执行
# ============================================================

@router.post("/run")
@limiter.limit(RATE_AGENT_RUN)
async def run_agent(
    request: Request,
    req: AgentExecutionRequest,
    _: bool = Depends(require_agent_exec),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    执行 Agent。

    模式:
      - single:     req.agent_name (单个 Agent)
      - sequential: req.context.agent_names (链式)
      - router:     req.context.candidates (路由分发)
      - debate:     req.context.agent_names (并行辩论)
    """
    # 查询用户实际权限 (role names → permission strings)
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.modules.tenant.models import User, UserRole
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(current_user.sub))
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    user = result.scalar_one_or_none()
    user_permissions = set()
    if user:
        for ur in (user.roles or []):
            user_permissions.update(ur.role.permissions or [])

    context = {
        "user_id": uuid.UUID(current_user.sub),
        "tenant_id": uuid.UUID(current_user.tenant_id),
        "permissions": list(user_permissions),
        **(req.context or {}),
    }

    mode = req.mode

    if mode == "single" or not mode:
        if not req.agent_name:
            return {"error": "single 模式需要指定 agent_name"}
        result = await orchestrator.run_single(
            req.agent_name, req.message, context,
        )

    elif mode == "sequential":
        agent_names = context.get("agent_names", [])
        if not agent_names:
            return {"error": "sequential 模式需要 context.agent_names"}
        result = await orchestrator.run_sequential(
            agent_names, req.message, context,
        )

    elif mode == "router":
        candidates = context.get("candidates", ["analyst", "support_agent", "reviewer"])
        result = await orchestrator.run_router(
            req.message, candidates, context,
        )

    elif mode == "debate":
        agent_names = context.get("agent_names", ["analyst", "reviewer", "support_agent"])
        result = await orchestrator.run_debate(
            agent_names, req.message, context,
        )

    else:
        return {"error": f"不支持的编排模式: {mode}"}

    return result


# ============================================================
# Stop Hook 管理
# ============================================================

@router.get("/stop-hook/status")
async def stop_hook_status(
    current_user: TokenPayload = Depends(get_current_user),
):
    """查看 Stop Hook 当前状态"""
    from app.modules.agent.stop_hook import stop_hook
    return {
        "stats": stop_hook.stats,
        "pending_approvals": len(stop_hook._pending_approvals),
        "dangerous_tools": list(stop_hook._dangerous_tools),
    }


@router.post("/stop-hook/abort")
async def stop_hook_abort(
    current_user: TokenPayload = Depends(get_current_user),
):
    """手动取消当前 Agent 执行"""
    from app.modules.agent.stop_hook import stop_hook
    stop_hook.abort()
    return {"message": "已发送取消信号", "stats": stop_hook.stats}


@router.post("/stop-hook/approve/{approval_id}")
async def stop_hook_approve(
    approval_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """审批通过某个危险操作"""
    from app.modules.agent.stop_hook import stop_hook
    ok = await stop_hook.approve(approval_id)
    if ok:
        return {"message": f"审批 {approval_id} 已通过", "approved": True}
    return {"message": f"审批 {approval_id} 不存在或已过期", "approved": False}


@router.post("/stop-hook/reject/{approval_id}")
async def stop_hook_reject(
    approval_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """拒绝审批并取消执行"""
    from app.modules.agent.stop_hook import stop_hook
    stop_hook.reject(approval_id)
    return {"message": f"审批 {approval_id} 已拒绝，执行已取消"}


# ============================================================
# 交付审计
# ============================================================

@router.post("/audit")
async def run_delivery_audit(
    body: AuditRequest,
    current_user: TokenPayload = Depends(get_current_user),
):
    """
    手动触发交付审计。

    检查: 需求完整性 / 步骤追踪 / 错误检查 / 输出质量 / 安全合规
    """
    from app.modules.agent.audit_hook import auditor

    auditor.set_requirements(body.requirements)
    auditor.set_steps(body.steps_executed)

    result = await auditor.audit(
        output=body.output,
        steps_executed=body.steps_executed,
        errors=body.errors,
    )

    return {
        "passed": result.passed,
        "blocked": result.blocked,
        "score": round(result.score, 4),
        "summary": result.summary,
        "dimensions": {k: v.value for k, v in result.dimensions.items()},
        "issues": [
            {
                "dimension": i.dimension,
                "severity": i.severity.value,
                "title": i.title,
                "detail": i.detail,
                "suggestion": i.suggestion,
            }
            for i in result.issues
        ],
        "fail_count": result.fail_count,
        "warn_count": result.warn_count,
    }


@router.get("/audit/dimensions")
async def audit_dimensions():
    """审计维度说明"""
    from app.modules.agent.audit_hook import auditor
    return {"dimensions": auditor.dimensions}
