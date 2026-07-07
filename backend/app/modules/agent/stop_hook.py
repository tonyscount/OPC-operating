"""
Agent Stop Hook — 执行中断/停止机制。

在 Agent 执行流程中插入多个检查点，满足条件时触发停止。

Stop 类型:
  1. HARD_STOP    — 立即终止，不可恢复 (安全违规)
  2. SOFT_STOP    — 暂停等待人工审批 (危险操作确认)
  3. BUDGET_STOP  — Token/费用预算耗尽
  4. ITERATION_STOP — 达到最大迭代次数
  5. USER_ABORT   — 用户手动取消
  6. TIMEOUT_STOP — 执行超时

用法:
    hook = StopHook()

    # 检查点 1: 每次 LLM 调用前
    await hook.check("before_llm_call", context={...})

    # 检查点 2: 工具调用前
    await hook.check("before_tool_call", context={"tool": "delete_user", ...})

    # 检查点 3: 每次迭代后
    await hook.check("after_iteration", context={"iteration": 5, ...})
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

from app.core.exceptions import ForbiddenException

logger = logging.getLogger("opc.agent.stop_hook")


# ============================================================
# Stop 类型
# ============================================================

class StopReason(str, Enum):
    HARD_STOP = "hard_stop"           # 安全违规，立即终止
    SOFT_STOP = "soft_stop"           # 暂停等待审批
    BUDGET_STOP = "budget_stop"       # 预算耗尽
    ITERATION_STOP = "iteration_stop" # 超过最大迭代
    USER_ABORT = "user_abort"         # 用户取消
    TIMEOUT_STOP = "timeout_stop"     # 超时


@dataclass
class StopSignal:
    """停止信号"""
    reason: StopReason
    message: str
    checkpoint: str                    # 触发检查点名称
    details: dict[str, Any] = field(default_factory=dict)
    can_resume: bool = False           # 是否可恢复
    requires_approval: bool = False    # 是否需要人工审批
    approval_id: str | None = None     # 审批 ID


# ============================================================
# Stop Hook
# ============================================================

class StopHook:
    """
    Agent 执行中断钩子。

    在编排器的关键节点注册检查点，满足条件时抛出 StopSignal。
    编排器捕获 StopSignal 后:
      - HARD_STOP → 立即终止，记录日志
      - SOFT_STOP → 等待人工审批 (通过 API 恢复)
      - BUDGET_STOP → 通知用户充值
      - ITERATION_STOP → 返回部分结果
    """

    def __init__(
        self,
        max_iterations: int = 30,
        max_tokens: int = 200_000,
        max_duration_seconds: int = 600,  # 10 分钟
        enable_dangerous_tool_block: bool = True,
    ):
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.max_duration_seconds = max_duration_seconds
        self.enable_dangerous_tool_block = enable_dangerous_tool_block

        # 运行时状态
        self._start_time: float | None = None
        self._iteration_count: int = 0
        self._total_tokens: int = 0
        self._abort_flag: bool = False
        self._pending_approvals: dict[str, StopSignal] = {}
        self._on_stop_callbacks: list[Callable[[StopSignal], Coroutine]] = []

        # 危险工具清单 (调用时触发 SOFT_STOP)
        self._dangerous_tools: set[str] = {
            "delete_user", "delete_document", "delete_role",
            "send_notification", "execute_sql",
        }

    # ============================================================
    # 检查点
    # ============================================================

    async def check(self, checkpoint: str, context: dict[str, Any] | None = None) -> None:
        """
        在编排器的关键节点调用此方法。

        checkpoint 名称:
          - "start"            : Agent 开始执行
          - "before_llm_call"  : 每次 LLM 调用前
          - "after_llm_call"   : 每次 LLM 调用后
          - "before_tool_call" : 工具调用前
          - "after_tool_call"  : 工具调用后
          - "after_iteration"  : 每次迭代后
          - "before_final_output": 输出最终答案前
        """
        ctx = context or {}

        if checkpoint == "start":
            self._start_time = time.perf_counter()
            self._iteration_count = 0
            self._total_tokens = 0
            self._abort_flag = False
            logger.info("[StopHook] Agent execution started")

        elif checkpoint == "before_tool_call":
            tool_name = ctx.get("tool_name", "")
            # 危险工具 → SOFT_STOP (等待审批)
            if self.enable_dangerous_tool_block and tool_name in self._dangerous_tools:
                signal = StopSignal(
                    reason=StopReason.SOFT_STOP,
                    message=f"危险操作 '{tool_name}' 需要人工审批",
                    checkpoint=checkpoint,
                    details={"tool_name": tool_name, "tool_args": ctx.get("tool_args", {})},
                    can_resume=True,
                    requires_approval=True,
                    approval_id=str(uuid.uuid4())[:8],
                )
                self._pending_approvals[signal.approval_id] = signal
                await self._emit(signal)
                raise StopHookException(signal)

        elif checkpoint == "after_iteration":
            self._iteration_count = ctx.get("iteration", self._iteration_count + 1)
            # 迭代次数超限
            if self._iteration_count >= self.max_iterations:
                signal = StopSignal(
                    reason=StopReason.ITERATION_STOP,
                    message=f"达到最大迭代次数 ({self.max_iterations})",
                    checkpoint=checkpoint,
                    details={"iterations": self._iteration_count},
                )
                await self._emit(signal)
                raise StopHookException(signal)

        elif checkpoint == "after_llm_call":
            tokens = ctx.get("tokens_used", 0)
            self._total_tokens += tokens
            # Token 预算超限
            if self._total_tokens >= self.max_tokens:
                signal = StopSignal(
                    reason=StopReason.BUDGET_STOP,
                    message=f"Token 预算耗尽 ({self._total_tokens}/{self.max_tokens})",
                    checkpoint=checkpoint,
                    details={"tokens_used": self._total_tokens, "budget": self.max_tokens},
                )
                await self._emit(signal)
                raise StopHookException(signal)

        # 通用检查
        await self._check_common_conditions(checkpoint, ctx)

    async def _check_common_conditions(self, checkpoint: str, ctx: dict) -> None:
        """通用停止条件检查"""
        # 用户手动取消
        if self._abort_flag:
            signal = StopSignal(
                reason=StopReason.USER_ABORT,
                message="用户手动取消执行",
                checkpoint=checkpoint,
            )
            await self._emit(signal)
            raise StopHookException(signal)

        # 超时
        if self._start_time:
            elapsed = time.perf_counter() - self._start_time
            if elapsed > self.max_duration_seconds:
                signal = StopSignal(
                    reason=StopReason.TIMEOUT_STOP,
                    message=f"执行超时 ({elapsed:.0f}s > {self.max_duration_seconds}s)",
                    checkpoint=checkpoint,
                    details={"elapsed_seconds": elapsed},
                )
                await self._emit(signal)
                raise StopHookException(signal)

    # ============================================================
    # 用户操作
    # ============================================================

    def abort(self) -> None:
        """用户手动取消"""
        self._abort_flag = True
        logger.info("[StopHook] User requested abort")

    def reset(self) -> None:
        """重置所有状态 (新一次执行)"""
        self._start_time = None
        self._iteration_count = 0
        self._total_tokens = 0
        self._abort_flag = False
        self._pending_approvals.clear()

    async def approve(self, approval_id: str) -> bool:
        """审批通过某个 SOFT_STOP"""
        if approval_id in self._pending_approvals:
            signal = self._pending_approvals.pop(approval_id)
            logger.info(f"[StopHook] Approved: {approval_id} — {signal.message}")
            return True
        return False

    def reject(self, approval_id: str) -> None:
        """拒绝审批"""
        if approval_id in self._pending_approvals:
            self._pending_approvals.pop(approval_id)
        self.abort()

    # ============================================================
    # 回调
    # ============================================================

    def on_stop(self, callback: Callable[[StopSignal], Coroutine]) -> None:
        """注册停止事件回调 (如飞书通知、日志写入)"""
        self._on_stop_callbacks.append(callback)

    async def _emit(self, signal: StopSignal) -> None:
        """触发所有停止回调"""
        for cb in self._on_stop_callbacks:
            try:
                await cb(signal)
            except Exception as e:
                logger.error(f"[StopHook] Callback error: {e}")

    @property
    def stats(self) -> dict:
        return {
            "iterations": self._iteration_count,
            "total_tokens": self._total_tokens,
            "elapsed_seconds": time.perf_counter() - self._start_time if self._start_time else 0,
            "aborted": self._abort_flag,
            "pending_approvals": len(self._pending_approvals),
        }


# ============================================================
# Stop Hook 异常 (编排器捕获)
# ============================================================

class StopHookException(Exception):
    """Stop Hook 触发的异常，编排器应捕获此异常并优雅停止"""

    def __init__(self, signal: StopSignal):
        self.signal = signal
        super().__init__(signal.message)


# ============================================================
# 全局单例
# ============================================================

stop_hook = StopHook()

# 注册默认回调: 日志
async def _log_stop(signal: StopSignal):
    logger.warning(
        f"[StopHook] STOP triggered: {signal.reason.value} "
        f"at {signal.checkpoint} — {signal.message}"
    )

stop_hook.on_stop(_log_stop)
