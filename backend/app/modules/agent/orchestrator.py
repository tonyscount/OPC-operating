"""
多智能体编排引擎 (基于 LangGraph)

支持模式:
  - single:    单个 Agent + Tool-calling Loop (ReAct)
  - sequential: AgentA → AgentB → AgentC (链式执行)
  - router:    根据用户意图路由到不同 Agent
  - debate:    3 Agent 并行 → 投票/综合结论

状态持久化: LangGraph Checkpointer → agent_executions 表
"""

import logging
import uuid
from typing import Annotated, Any, Literal

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import MemorySaver
from typing_extensions import TypedDict

from app.config import settings

logger = logging.getLogger("opc.agent.orchestrator")


# ============================================================
# Agent 状态定义 (LangGraph State)
# ============================================================

class AgentState(TypedDict):
    """多 Agent 共享状态"""
    messages: Annotated[list[dict], "append"]  # 消息历史
    current_agent: str | None  # 当前活跃 Agent
    next_agent: str | None     # 下一个 Agent (Sequential 模式)
    agent_outputs: dict[str, str]  # 各 Agent 输出: {agent_name: output}
    final_output: str | None   # 最终输出
    vote_results: dict | None  # 投票结果 (Debate 模式)
    context: dict              # 用户上下文 {tenant_id, user_id, ...}
    iteration: int             # 当前迭代次数


# ============================================================
# Agent 定义
# ============================================================

class AgentDefinition:
    """一个 Agent 的完整定义 (可来自 DB 或代码注册)"""

    def __init__(
        self,
        name: str,
        role_prompt: str,
        description: str = "",
        emoji: str = "🤖",
        tools: list[str] | None = None,
        knowledge_base_ids: list[str] | None = None,
        model: str = "",
        temperature: float = 0.3,
        max_iterations: int = 10,
    ):
        self.name = name
        self.role_prompt = role_prompt
        self.description = description
        self.emoji = emoji
        self.tools = tools or []
        self.knowledge_base_ids = knowledge_base_ids or []
        self.model = model or settings.LLM_MODEL
        self.temperature = temperature
        self.max_iterations = max_iterations


# ============================================================
# LLM 调用 (抽象层)
# ============================================================

class LLMClient:
    """LLM 客户端 — 封装 OpenAI 兼容 API。默认使用 settings.LLM_MODEL。"""

    def __init__(self, model: str = "", temperature: float = 0.3):
        self.model = model or settings.LLM_MODEL
        self.temperature = temperature

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """调用 LLM 聊天 (支持 function calling) + 可观测性记录"""
        import time as _time
        from app.core.ai_metrics import metrics as ai_metrics

        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        t0 = _time.perf_counter()
        response = await client.chat.completions.create(**kwargs)
        elapsed = (_time.perf_counter() - t0) * 1000

        choice = response.choices[0]

        # AI 可观测性: 记录 token 消耗
        usage = response.usage
        if usage:
            ai_metrics.record(
                model=self.model,
                input_tokens=usage.prompt_tokens or 0,
                output_tokens=usage.completion_tokens or 0,
                duration_ms=elapsed,
            )

        result = {
            "role": "assistant",
            "content": choice.message.content or "",
            "_metrics": {
                "model": self.model,
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0,
                "duration_ms": round(elapsed, 1),
            } if usage else {},
        }

        if choice.message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        return result

# ============================================================
# LangGraph 编排器
# ============================================================

class AgentOrchestrator:
    """
    多 Agent 编排器。

    用法:
        orch = AgentOrchestrator()
        orch.register_agent(AgentDefinition(...))

        result = await orch.run_single("analyst", "分析这份数据...", context={})
    """

    def __init__(self):
        self._agents: dict[str, AgentDefinition] = {}
        self._llm_clients: dict[str, LLMClient] = {}
        self._graphs: dict[str, CompiledStateGraph] = {}
        self._checkpointer = self._create_checkpointer()

    def _create_checkpointer(self):
        """创建 Checkpointer: 优先 PostgresSaver，回退 MemorySaver"""
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from app.config import settings
            saver = PostgresSaver.from_conn_string(settings.DATABASE_URL_SYNC)
            saver.setup()
            logger.info("Checkpointer: PostgresSaver initialized")
            return saver
        except Exception as e:
            logger.warning(f"PostgresSaver unavailable ({e}), using MemorySaver")
            return MemorySaver()

    def register_agent(self, agent: AgentDefinition) -> None:
        """注册 Agent 定义"""
        self._agents[agent.name] = agent
        self._llm_clients[agent.name] = LLMClient(
            model=agent.model,
            temperature=agent.temperature,
        )
        logger.info(f"Agent registered: {agent.name}")

    def get_agent(self, name: str) -> AgentDefinition | None:
        return self._agents.get(name)

    def list_agents(self) -> list[dict]:
        """列出所有 Agent 定义 (供前端/API)"""
        return [
            {
                "name": a.name,
                "emoji": a.emoji,
                "description": a.description,
                "role_prompt": a.role_prompt[:200],
                "tools": a.tools,
                "model": a.model,
            }
            for a in self._agents.values()
        ]

    # ============================================================
    # ============================================================
    # 模式 1: Single Agent (ReAct Loop)
    # ============================================================

    async def run_single(
        self, agent_name: str, user_message: str,
        context: dict | None = None, thread_id: str | None = None,
    ) -> dict:
        """单个 Agent 执行 ReAct 模式。"""
        ctx = context or {}
        tid = thread_id or str(uuid.uuid4())

        agent = self._agents.get(agent_name)
        if not agent:
            error_result = {"error": f"Agent '{agent_name}' 未注册", "output": None}
            await self._persist_execution(
                tenant_id=str(ctx.get("tenant_id", "")),
                agent_name=agent_name,
                orchestration_mode="single",
                input_message=user_message,
                output_message=None,
                thread_id=tid,
                total_steps=0,
                total_tokens=0,
                state_snapshot={},
                status="failed",
                error_message=f"Agent '{agent_name}' 未注册",
            )
            return error_result

        llm = self._llm_clients[agent_name]
        tools = self._build_tools_schema(agent.tools)
        messages = [{"role": "system", "content": agent.role_prompt}, {"role": "user", "content": user_message}]

        # ReAct Loop
        try:
            final_output, step_count, message_log, stop_info, total_tokens = await self._react_loop(
                agent, llm, messages, tools, tid, ctx,
            )
        except Exception as e:
            logger.error(f"[Orchestrator] LLM call failed: {e}")
            error_result = {
                "agent_name": agent_name,
                "output": None,
                "error": f"LLM 调用失败: {str(e)}",
                "steps": 0,
                "thread_id": tid,
                "stopped": False,
                "messages": [],
            }
            await self._persist_execution(
                tenant_id=str(ctx.get("tenant_id", "")),
                agent_name=agent_name,
                orchestration_mode="single",
                input_message=user_message,
                output_message=None,
                thread_id=tid,
                total_steps=0,
                total_tokens=0,
                state_snapshot=error_result,
                status="failed",
                error_message=f"LLM error: {str(e)[:200]}",
            )
            return error_result

        # 交付审计
        audit_result = await self._run_audit(agent_name, final_output, message_log)

        result = self._build_result(agent_name, final_output, step_count, tid, message_log, stop_info, audit_result)

        # 持久化执行记录到 agent_executions 表
        status = "completed"
        error_message = None
        if result.get("error"):
            status = "failed"
            error_message = result.get("error")
        elif result.get("stopped"):
            status = "cancelled" if result.get("can_resume") else "stopped"
            error_message = result.get("stop_reason")

        await self._persist_execution(
            tenant_id=str(ctx.get("tenant_id", "")),
            agent_name=agent_name,
            orchestration_mode="single",
            input_message=user_message,
            output_message=result.get("output"),
            thread_id=tid,
            total_steps=step_count,
            total_tokens=total_tokens,
            state_snapshot=result,
            status=status,
            error_message=error_message,
        )
        return result

    async def _react_loop(self, agent, llm, messages, tools, tid, ctx) -> tuple:
        """ReAct 循环: LLM调用 → 工具执行 → 观察 → 重复"""
        from app.modules.agent.stop_hook import StopHookException, stop_hook

        stop_hook.reset()
        stop_hook.max_iterations = agent.max_iterations
        await stop_hook.check("start", {"agent": agent.name, "thread_id": tid})

        step_count, final_output, message_log, total_tokens = 0, "", [], 0
        stop_info = None

        try:
            while step_count < agent.max_iterations:
                step_count += 1
                await stop_hook.check("before_llm_call", {"iteration": step_count})

                response = await llm.chat(messages, tools=tools if tools else None)
                metrics = response.get("_metrics", {})
                total_tokens += metrics.get("input_tokens", 0) + metrics.get("output_tokens", 0)
                # 构建 assistant 消息，含 tool_calls（DeepSeek 要求）
                asst_msg = {"role": "assistant", "content": response.get("content", "")}
                if response.get("tool_calls"):
                    asst_msg["tool_calls"] = response["tool_calls"]
                messages.append(asst_msg)
                await stop_hook.check("after_llm_call", {"iteration": step_count, "tokens_used": len(str(response)) // 4})

                if not response.get("tool_calls"):
                    final_output = response.get("content", "")
                    message_log.append({"step": step_count, "type": "assistant", "content": final_output})
                    break

                for tc in response["tool_calls"]:
                    tool_name = tc.get("function", {}).get("name", tc.get("name", ""))
                    tool_args = tc.get("function", {}).get("arguments", tc.get("arguments", "{}"))
                    await stop_hook.check("before_tool_call", {"tool_name": tool_name, "tool_args": tool_args})
                    tool_result = await self._execute_tool(tool_name, tool_args, ctx)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": str(tool_result)})
                    message_log.append({"step": step_count, "type": "tool_call", "tool": tool_name, "arguments": tool_args, "result": str(tool_result)[:500]})

                await stop_hook.check("after_iteration", {"iteration": step_count})

        except StopHookException as e:
            logger.warning(f"[Orchestrator] Stopped: {e.signal.reason.value} — {e.signal.message}")
            stop_info = {"reason": e.signal.reason.value, "details": e.signal.details, "approval_id": e.signal.approval_id, "can_resume": e.signal.can_resume}

        return final_output, step_count, message_log, stop_info, total_tokens

    async def _run_audit(self, agent_name: str, output: str, message_log: list) -> dict | None:
        """交付前审计"""
        try:
            from app.modules.agent.audit_hook import auditor as audit_hook
            audit_hook.set_requirements([f"Agent {agent_name} 正确执行", "输出为中文", "基于工具调用结果回答"])
            return await audit_hook.audit(output=output, steps_executed=[m.get("type", "") for m in message_log], errors=[], execution_log=message_log)
        except Exception as e:
            logger.error(f"Audit failed: {e}")
            return None

    def _build_result(self, agent_name, output, steps, tid, log, stop_info, audit) -> dict:
        """组装最终结果"""
        result = {"agent_name": agent_name, "output": output or "Agent 达到最大迭代次数", "steps": steps, "thread_id": tid, "messages": log}
        if stop_info:
            result.update({"stopped": True, "stop_reason": stop_info["reason"], "stop_details": stop_info["details"], "approval_id": stop_info["approval_id"], "can_resume": stop_info["can_resume"]})
            result["output"] = output or f"执行被中断: {stop_info.get('reason', 'unknown')}"
        else:
            result["stopped"] = False
        if audit:
            result["audit"] = {"passed": audit.passed, "score": audit.score, "summary": audit.summary or "审计未运行",
                "issues": [{"dimension": i.dimension, "severity": i.severity.value, "title": i.title, "suggestion": i.suggestion} for i in audit.issues]}
        return result

    async def _persist_execution(
        self,
        tenant_id: str,
        agent_name: str,
        orchestration_mode: str,
        input_message: str,
        output_message: str | None,
        thread_id: str,
        total_steps: int,
        total_tokens: int,
        state_snapshot: dict | None,
        status: str,
        error_message: str | None,
    ) -> None:
        """持久化执行记录到 agent_executions 表。使用 async_session_factory() 获取独立 DB 会话。"""
        if not tenant_id:
            logger.warning(f"Skipping execution persistence: no tenant_id (thread={thread_id})")
            return
        try:
            from app.core.database import async_session_factory
            from app.modules.agent.models import AgentExecution
            import uuid as _uuid

            async with async_session_factory() as db:
                execution = AgentExecution(
                    tenant_id=_uuid.UUID(tenant_id),
                    thread_id=thread_id,
                    orchestration_mode=orchestration_mode,
                    status=status,
                    input_message=input_message,
                    output_message=output_message,
                    total_steps=total_steps,
                    total_tokens=total_tokens,
                    state_snapshot=state_snapshot or {},
                    error_message=error_message,
                )
                db.add(execution)
                await db.commit()
                logger.debug(f"Execution persisted: {thread_id} mode={orchestration_mode} status={status}")
        except Exception as e:
            logger.error(f"Failed to persist execution ({thread_id}): {e}")

    # ============================================================
    # 模式 2: Sequential (链式)
    # ============================================================

    async def run_sequential(
        self,
        agent_names: list[str],
        user_message: str,
        context: dict | None = None,
    ) -> dict:
        """
        顺序执行: AgentA → AgentB → AgentC

        每个 Agent 的输出作为下一个 Agent 的输入。
        """
        context = context or {}
        current_input = user_message
        outputs = {}

        for name in agent_names:
            agent = self._agents.get(name)
            if not agent:
                outputs[name] = f"Agent '{name}' 未注册"
                continue

            # 为后续 Agent 添加上下文
            if outputs:
                prev_context = "\n".join(
                    f"[{n}]: {o}" for n, o in outputs.items()
                )
                current_input = f"前序分析:\n{prev_context}\n\n用户原始问题:\n{user_message}"

            result = await self.run_single(name, current_input, context)
            outputs[name] = result["output"]
            current_input = result["output"]

        final_output = outputs.get(agent_names[-1], "")
        seq_result = {
            "mode": "sequential",
            "agent_outputs": outputs,
            "final_output": final_output,
            "execution_order": agent_names,
        }

        # 持久化顺序执行汇总记录
        await self._persist_execution(
            tenant_id=str(context.get("tenant_id", "")),
            agent_name=",".join(agent_names),
            orchestration_mode="sequential",
            input_message=user_message,
            output_message=final_output,
            thread_id=str(uuid.uuid4()),
            total_steps=len(agent_names),
            total_tokens=0,
            state_snapshot=seq_result,
            status="completed",
            error_message=None,
        )
        return seq_result

    # ============================================================
    # 模式 3: Router (意图路由)
    # ============================================================

    async def run_router(
        self,
        user_message: str,
        candidates: list[str],
        context: dict | None = None,
    ) -> dict:
        """
        路由分发: 用轻量 Router LLM 判断意图 → 分发给最合适的 Agent。

        Router Prompt 分析用户输入，选择最匹配的 Agent。
        """
        context = context or {}
        candidates_str = "\n".join(
            f"- {name}: {self._agents[name].role_prompt[:100]}" if name in self._agents
            else f"- {name}: (未注册)"
            for name in candidates
        )

        router_prompt = f"""你是路由分发器。根据用户输入选择最合适的 Agent。

可用 Agent:
{candidates_str}

请只回复一个 Agent 名称 (精确匹配)，不要解释。"""

        llm = LLMClient(model="gpt-4o", temperature=0)
        response = await llm.chat([
            {"role": "system", "content": router_prompt},
            {"role": "user", "content": user_message},
        ])

        selected = response.get("content", "").strip()
        if selected not in self._agents:
            selected = candidates[0]  # fallback

        single_result = await self.run_single(selected, user_message, context)

        router_result = {
            "mode": "router",
            "selected_agent": selected,
            "output": single_result["output"],
            "steps": single_result["steps"],
        }

        # 持久化路由执行记录
        await self._persist_execution(
            tenant_id=str(context.get("tenant_id", "")),
            agent_name=selected,
            orchestration_mode="router",
            input_message=user_message,
            output_message=single_result["output"],
            thread_id=str(uuid.uuid4()),
            total_steps=single_result.get("steps", 0),
            total_tokens=0,
            state_snapshot=router_result,
            status="completed",
            error_message=None,
        )
        return router_result

    # ============================================================
    # 模式 4: Debate / Voting
    # ============================================================

    async def run_debate(
        self,
        agent_names: list[str],
        topic: str,
        context: dict | None = None,
        rounds: int = 1,
    ) -> dict:
        """
        辩论/投票模式: 多个 Agent 并行分析 → 汇总投票 → 综合结论。
        """
        import asyncio

        context = context or {}

        # 第 1 轮: 并行分析
        async def analyze(name: str) -> dict:
            result = await self.run_single(name, topic, context)
            return {"agent": name, "analysis": result["output"]}

        analyses = await asyncio.gather(*[analyze(n) for n in agent_names])

        # 综合评估 (使用最后一个 Agent 或专门的 Judge)
        debate_transcript = "\n\n".join(
            f"## {a['agent']}\n{a['analysis']}" for a in analyses
        )

        judge_prompt = f"""你是评审员。以下是 {len(agent_names)} 个 Agent 对问题的分析，请综合各方观点给出最终结论。

{debate_transcript}

请给出:
1. 综合结论
2. 各方观点的共同点和分歧
3. 投票结果 (哪个方案最优)"""

        judge_result = await self.run_single(
            agent_names[0],  # 复用第一个 Agent 的 LLM 做 Judge
            f"问题: {topic}\n\n请综合以下分析给出结论:\n{debate_transcript}",
            context,
        )

        debate_result = {
            "mode": "debate",
            "analyses": analyses,
            "final_output": judge_result["output"],
            "agent_count": len(agent_names),
        }

        # 持久化辩论执行记录
        await self._persist_execution(
            tenant_id=str(context.get("tenant_id", "")),
            agent_name=",".join(agent_names),
            orchestration_mode="debate",
            input_message=topic,
            output_message=judge_result["output"],
            thread_id=str(uuid.uuid4()),
            total_steps=len(agent_names) + 1,  # N analyses + 1 judge
            total_tokens=0,
            state_snapshot=debate_result,
            status="completed",
            error_message=None,
        )
        return debate_result

    # ============================================================
    # 工具执行
    # ============================================================

    def _build_tools_schema(self, tool_names: list[str]) -> list[dict]:
        """从 Skill 注册表构建 OpenAI function calling schema"""
        from app.modules.skill.registry import skill_registry

        schemas = []
        for name in tool_names:
            skill = skill_registry.get(name)
            if not skill:
                continue
            params = {}
            for pname, pdef in skill["parameters_schema"].items():
                params[pname] = {
                    "type": pdef.get("type", "string"),
                    "description": pdef.get("description", ""),
                }
            required = [
                pname for pname, pdef in skill["parameters_schema"].items()
                if pdef.get("required", False)
            ]

            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": skill["description"],
                    "parameters": {
                        "type": "object",
                        "properties": params,
                        "required": required,
                    },
                },
            })
        return schemas

    async def _execute_tool(self, tool_name: str, arguments: str, context: dict) -> Any:
        """执行工具调用 (通过 Skill Executor)"""
        import json
        from app.modules.skill.executor import executor

        try:
            params = json.loads(arguments) if isinstance(arguments, str) else arguments
        except json.JSONDecodeError:
            params = {"raw": arguments}

        result = await executor.execute(
            tool_name, params,
            user_id=context.get("user_id"),
            tenant_id=context.get("tenant_id"),
            user_permissions=context.get("permissions", []),
        )
        return result.get("result") if result["success"] else result.get("error")


# ============================================================
# 全局单例
# ============================================================

orchestrator = AgentOrchestrator()
