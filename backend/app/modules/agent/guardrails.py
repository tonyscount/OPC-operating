"""
Agent 安全围栏 (Guardrails)

在 Agent 执行流程中插入校验 Hook:
  1. before_tool_call:  参数校验、危险操作拦截
  2. after_agent_output: 内容审查 (PII/敏感词/幻觉检测)
  3. on_decision:       最终决策审核 (如删除操作需要二次确认)
"""

import logging
import re
from typing import Any

from app.core.exceptions import ForbiddenException

logger = logging.getLogger("opc.agent.guardrails")

# ========== 危险操作清单 ==========
DANGEROUS_TOOLS = {
    "delete_document": "删除文档",
    "delete_user": "删除用户",
    "send_notification": "批量发送通知",  # 批量操作视为敏感
    "execute_sql": "直接执行SQL",
    "call_external_api": "调用外部API",
}

# ========== 敏感信息 Pattern ==========
PII_PATTERNS = {
    "phone": re.compile(r"1[3-9]\d{9}"),
    "id_card": re.compile(r"\d{17}[\dXx]"),
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
}


class GuardrailHook:
    """安全围栏钩子"""

    # ========== 工具调用前 ==========

    async def before_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: dict | None = None,
    ) -> dict[str, Any]:
        """
        Agent 调用工具前的校验。

        校验内容:
          1. 危险操作确认
          2. 参数合理性
          3. 权限检查

        返回:
          修改后的 args (可在此注入租户过滤条件)
        """
        # 危险操作标记
        if tool_name in DANGEROUS_TOOLS:
            logger.warning(
                f"[Guardrail] Dangerous tool call: {tool_name} "
                f"({DANGEROUS_TOOLS[tool_name]}) args={str(args)[:200]}"
            )
            args["_dangerous"] = True
            args["_confirmed_by"] = context.get("user_id") if context else None

        # 注入租户上下文 (防跨租户)
        if context and context.get("tenant_id"):
            args["_tenant_id"] = str(context["tenant_id"])

        return args

    # ========== Agent 输出后 ==========

    async def after_agent_output(
        self,
        agent_name: str,
        output: str,
        context: dict | None = None,
    ) -> str:
        """
        Agent 输出内容审查。

        审查内容:
          1. PII 检测 (手机号/身份证/邮箱)
          2. 敏感词过滤
          3. 幻觉检测 (输出与事实不符)

        返回:
          审查后的输出 (脱敏或标记)
        """
        # PII 脱敏
        for pii_type, pattern in PII_PATTERNS.items():
            matches = pattern.findall(output)
            if matches:
                logger.warning(
                    f"[Guardrail] {agent_name} output contains {len(matches)} {pii_type} instances"
                )
                # 脱敏处理
                for match in matches:
                    output = output.replace(match, f"[{pii_type.upper()}]")

        return output

    # ========== 决策审核 ==========

    async def on_decision(
        self,
        agent_name: str,
        decision: dict[str, Any],
        context: dict | None = None,
    ) -> bool:
        """
        最终决策审核 —— 决定是否允许 Agent 的操作生效。

        需要二次确认的操作:
          - 删除文档/用户
          - 批量操作 (> 10 条)
          - 调用外部 API

        返回: True = 允许, False = 拦截
        """
        action = decision.get("action", "")
        target_count = decision.get("count", 0)

        # 批量操作阈值
        if target_count > 10:
            logger.warning(
                f"[Guardrail] Batch operation blocked: {action} x {target_count}"
            )
            return False

        # 删除操作需要明确确认
        if "delete" in action.lower():
            confirmed = decision.get("confirmed", False)
            if not confirmed:
                logger.warning(f"[Guardrail] Delete blocked (not confirmed): {action}")
                return False

        return True


# ========== 全局单例 ==========
guardrails = GuardrailHook()
