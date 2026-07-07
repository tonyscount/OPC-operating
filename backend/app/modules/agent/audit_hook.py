"""
交付审计 Hook — 任务完成后全面审计，通过才能交付。

审计维度:
  1. 完整性检查 — 需求项是否全部覆盖
  2. 步骤检查   — 计划步骤是否全部执行，无跳步
  3. 错误检查   — 执行过程中是否有未处理的错误
  4. 输出检查   — 输出是否为空/截断/格式错误
  5. 安全合规   — 是否访问了不该访问的数据
  6. 质量标准   — 代码规范、注释、测试覆盖

用法:
    auditor = DeliveryAuditor(requirements=[...], steps=[...])
    result = await auditor.audit(execution_result, messages_log)
    if not result.passed:
        raise DeliveryBlockedException(result)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("opc.agent.audit")


# ============================================================
# 审计结果
# ============================================================

class AuditStatus(str, Enum):
    PASS = "pass"       # 通过
    WARN = "warn"       # 警告 (不阻塞交付，但需关注)
    FAIL = "fail"       # 失败 (阻塞交付，必须修复)
    SKIPPED = "skipped" # 跳过 (该维度不适用)


@dataclass
class AuditIssue:
    """单个审计发现问题"""
    dimension: str          # 审计维度
    severity: AuditStatus   # 严重程度
    title: str              # 问题标题
    detail: str             # 详细描述
    location: str = ""      # 出错位置 (代码文件/步骤名称)
    suggestion: str = ""    # 修复建议


@dataclass
class AuditResult:
    """一次完整审计的结果"""
    passed: bool = True                        # 是否通过 (无 FAIL)
    dimensions: dict[str, AuditStatus] = field(default_factory=dict)
    issues: list[AuditIssue] = field(default_factory=list)
    summary: str = ""
    blocked: bool = False                      # 是否阻塞交付
    score: float = 1.0                         # 0.0-1.0

    @property
    def fail_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == AuditStatus.FAIL)

    @property
    def warn_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == AuditStatus.WARN)


# ============================================================
# 交付审计器
# ============================================================

class DeliveryAuditor:
    """
    交付前全面审计。

    用法:
        auditor = DeliveryAuditor()
        auditor.set_requirements(["用户登录", "知识库搜索", "RAG问答"])
        auditor.set_steps(["初始化DB", "创建模型", "编写API", "测试"])

        result = await auditor.audit(
            output="...",
            steps_executed=["初始化DB", "创建模型"],
            errors=[],
            execution_log=[],
        )

        if not result.passed:
            print(f"阻塞交付: {result.summary}")
            for issue in result.issues:
                print(f"  [{issue.severity}] {issue.title}")
    """

    def __init__(self):
        self._requirements: list[str] = []
        self._required_steps: list[str] = []
        self._quality_checks_enabled: bool = True
        self._security_checks_enabled: bool = True

        # 审计维度 & 权重
        self.dimensions = {
            "completeness":   "需求完整性",
            "step_trace":     "步骤追踪",
            "error_check":    "错误检查",
            "output_quality": "输出质量",
            "security":       "安全合规",
            "code_quality":   "代码规范",
        }

    def set_requirements(self, reqs: list[str]) -> None:
        """设置需求清单"""
        self._requirements = reqs

    def set_steps(self, steps: list[str]) -> None:
        """设置计划步骤"""
        self._required_steps = steps

    def add_requirement(self, req: str) -> None:
        self._requirements.append(req)

    def add_step(self, step: str) -> None:
        self._required_steps.append(step)

    # ============================================================
    # 主审计流程
    # ============================================================

    async def audit(
        self,
        output: Any,
        steps_executed: list[str] | None = None,
        errors: list[str] | None = None,
        execution_log: list[dict] | None = None,
        source_code_paths: list[str] | None = None,
    ) -> AuditResult:
        """
        执行全面审计。

        参数:
          output:           最终输出内容
          steps_executed:   实际执行的步骤列表
          errors:           执行过程中记录的错误
          execution_log:    执行日志
          source_code_paths:涉及的源代码文件路径
        """
        result = AuditResult()
        steps_executed = steps_executed or []
        errors = errors or []
        execution_log = execution_log or []

        # ===== 维度 1: 需求完整性 =====
        await self._audit_completeness(result, output, steps_executed)

        # ===== 维度 2: 步骤追踪 =====
        await self._audit_step_trace(result, steps_executed)

        # ===== 维度 3: 错误检查 =====
        await self._audit_errors(result, errors, execution_log)

        # ===== 维度 4: 输出质量 =====
        await self._audit_output_quality(result, output)

        # ===== 维度 5: 安全合规 =====
        if self._security_checks_enabled:
            await self._audit_security(result, output, execution_log)

        # ===== 维度 6: 代码规范 =====
        if self._quality_checks_enabled and source_code_paths:
            await self._audit_code_quality(result, source_code_paths)

        # 汇总
        result.passed = result.fail_count == 0
        result.blocked = result.fail_count > 0
        result.score = self._calculate_score(result)

        if result.passed:
            result.summary = f"✅ 审计通过 — {len(result.issues)} 个提示"
        else:
            result.summary = (
                f"❌ 审计未通过 — {result.fail_count} 个阻断问题, "
                f"{result.warn_count} 个警告"
            )

        logger.info(
            f"[Audit] {result.summary} (score={result.score:.0%}, "
            f"dimensions={dict(result.dimensions)})"
        )

        return result

    # ============================================================
    # 各维度审计实现
    # ============================================================

    async def _audit_completeness(
        self, result: AuditResult, output: Any, steps: list[str],
    ) -> None:
        """检查需求是否全部覆盖"""
        if not self._requirements:
            result.dimensions["completeness"] = AuditStatus.SKIPPED
            return

        output_str = str(output).lower() if output else ""
        all_ok = True
        has_warn = False

        for req in self._requirements:
            # 简单检查: 输出中是否提到了需求关键词
            keywords = req.lower().split()
            matched = any(kw in output_str for kw in keywords)

            if not matched:
                result.issues.append(AuditIssue(
                    dimension="completeness",
                    severity=AuditStatus.FAIL,
                    title=f"未覆盖需求: {req}",
                    detail=f"输出中未找到与 '{req}' 相关的内容",
                    suggestion=f"请确保实现覆盖了需求: {req}",
                ))
                all_ok = False
            else:
                # 检查是否只是提及但没有实际实现
                if len(output_str) < 50:
                    result.issues.append(AuditIssue(
                        dimension="completeness",
                        severity=AuditStatus.WARN,
                        title=f"需求覆盖存疑: {req}",
                        detail=f"输出过短，可能未完整实现 '{req}'",
                        suggestion="请提供更详细的实现",
                    ))
                    has_warn = True

        if all_ok and not has_warn:
            result.dimensions["completeness"] = AuditStatus.PASS
        elif all_ok:
            result.dimensions["completeness"] = AuditStatus.WARN
        else:
            result.dimensions["completeness"] = AuditStatus.FAIL

    async def _audit_step_trace(
        self, result: AuditResult, steps_executed: list[str],
    ) -> None:
        """检查计划步骤是否全部执行，无跳步"""
        if not self._required_steps:
            result.dimensions["step_trace"] = AuditStatus.SKIPPED
            return

        executed_set = set(s.lower() for s in steps_executed)
        all_ok = True

        for i, step in enumerate(self._required_steps):
            step_lower = step.lower()
            # 模糊匹配
            matched = any(
                step_lower in ex or ex in step_lower
                for ex in executed_set
            )

            if not matched:
                result.issues.append(AuditIssue(
                    dimension="step_trace",
                    severity=AuditStatus.FAIL,
                    title=f"步骤 {i + 1} 未执行: {step}",
                    detail=f"计划中的步骤 '{step}' 在实际执行中未找到",
                    location=f"步骤 #{i + 1}",
                    suggestion=f"请执行缺失的步骤: {step}",
                ))
                all_ok = False

        # 检查是否有计划外的步骤 (跳步信号)
        planned_set = set(s.lower() for s in self._required_steps)
        for ex in steps_executed:
            if not any(ex in p or p in ex for p in planned_set):
                result.issues.append(AuditIssue(
                    dimension="step_trace",
                    severity=AuditStatus.WARN,
                    title=f"计划外步骤: {ex}",
                    detail="执行了计划中未列出的步骤",
                    suggestion="请确认是否为必要步骤，如是请更新计划",
                ))

        result.dimensions["step_trace"] = (
            AuditStatus.PASS if all_ok else AuditStatus.FAIL
        )

    async def _audit_errors(
        self, result: AuditResult, errors: list[str], log: list[dict],
    ) -> None:
        """检查执行过程中是否有未处理的错误"""
        has_errors = False
        has_warnings = False

        # 显式错误
        for err in errors:
            result.issues.append(AuditIssue(
                dimension="error_check",
                severity=AuditStatus.FAIL,
                title="执行中出现错误",
                detail=err,
                suggestion="请修复该错误后重新执行",
            ))
            has_errors = True

        # 日志中的异常
        for entry in log:
            if entry.get("type") == "error":
                result.issues.append(AuditIssue(
                    dimension="error_check",
                    severity=AuditStatus.FAIL,
                    title=f"步骤 {entry.get('step')} 出现异常",
                    detail=str(entry.get("result", ""))[:500],
                ))
                has_errors = True

            # tool_call 返回 error
            if entry.get("type") == "tool_call":
                tool_result = str(entry.get("result", "")).lower()
                if "error" in tool_result or "fail" in tool_result:
                    result.issues.append(AuditIssue(
                        dimension="error_check",
                        severity=AuditStatus.WARN,
                        title=f"工具 {entry.get('tool')} 可能返回错误",
                        detail=str(entry.get("result", ""))[:300],
                    ))
                    has_warnings = True

        if has_errors:
            result.dimensions["error_check"] = AuditStatus.FAIL
        elif has_warnings:
            result.dimensions["error_check"] = AuditStatus.WARN
        else:
            result.dimensions["error_check"] = AuditStatus.PASS

    async def _audit_output_quality(
        self, result: AuditResult, output: Any,
    ) -> None:
        """检查输出质量"""
        if output is None:
            result.issues.append(AuditIssue(
                dimension="output_quality",
                severity=AuditStatus.FAIL,
                title="输出为空 (None)",
                detail="任务执行完成但未产生输出",
                suggestion="请检查执行流程是否正确返回结果",
            ))
            result.dimensions["output_quality"] = AuditStatus.FAIL
            return

        output_str = str(output)
        issues_found = False

        # 空字符串
        if not output_str.strip():
            result.issues.append(AuditIssue(
                dimension="output_quality",
                severity=AuditStatus.FAIL,
                title="输出为空字符串",
                detail="任务返回了空内容",
                suggestion="请检查是否正常处理了输入",
            ))
            issues_found = True

        # 截断检测
        truncation_markers = ["...", "略", "省略", "[truncated]", "等等"]
        for marker in truncation_markers:
            if output_str.rstrip().endswith(marker):
                result.issues.append(AuditIssue(
                    dimension="output_quality",
                    severity=AuditStatus.WARN,
                    title=f"输出可能被截断 (末尾为 '{marker}')",
                    detail="输出末尾存在截断标记",
                    suggestion="请提供完整输出或明确标注截断原因",
                ))
                break

        # 过短 (可能未完成)
        if len(output_str) < 20:
            result.issues.append(AuditIssue(
                dimension="output_quality",
                severity=AuditStatus.WARN,
                title=f"输出过短 ({len(output_str)} 字符)",
                detail="输出长度异常，可能任务未完整执行",
                suggestion="请检查任务是否完整完成",
            ))

        # 包含未替换的占位符
        placeholders = ["TODO", "FIXME", "XXX", "PLACEHOLDER", "待实现", "待完成"]
        for ph in placeholders:
            if ph.lower() in output_str.lower():
                result.issues.append(AuditIssue(
                    dimension="output_quality",
                    severity=AuditStatus.FAIL,
                    title=f"输出中包含未完成的占位符: '{ph}'",
                    detail="输出中存在 TODO/占位符，表明有未完成的工作",
                    suggestion=f"请完成 '{ph}' 标记的内容后再交付",
                ))
                issues_found = True

        if issues_found:
            result.dimensions["output_quality"] = AuditStatus.FAIL
        else:
            result.dimensions["output_quality"] = AuditStatus.PASS

    async def _audit_security(
        self, result: AuditResult, output: Any, log: list[dict],
    ) -> None:
        """安全检查"""
        output_str = str(output).lower() if output else ""
        issues_found = False

        # API Key 泄漏
        api_key_patterns = [
            "sk-", "api_key=", "api-key:", "bearer ", "authorization:",
        ]
        for pattern in api_key_patterns:
            if pattern in output_str:
                result.issues.append(AuditIssue(
                    dimension="security",
                    severity=AuditStatus.FAIL,
                    title=f"潜在密钥泄漏: '{pattern}'",
                    detail="输出中可能包含 API Key 或敏感凭证",
                    suggestion="请移除所有密钥和凭证后再交付",
                ))
                issues_found = True

        # PII 检查 (简单版)
        import re
        phone_pattern = re.compile(r"1[3-9]\d{9}")
        if phone_pattern.search(str(output)):
            result.issues.append(AuditIssue(
                dimension="security",
                severity=AuditStatus.WARN,
                title="输出中包含手机号",
                detail="输出中检测到疑似手机号",
                suggestion="请脱敏处理后再交付",
            ))

        # 跨租户数据检查
        for entry in log:
            if entry.get("type") == "tool_call":
                args = str(entry.get("arguments", ""))
                if "_tenant_id" not in args and "tenant_id" in args:
                    result.issues.append(AuditIssue(
                        dimension="security",
                        severity=AuditStatus.WARN,
                        title="工具调用可能缺少租户过滤",
                        detail=f"工具 {entry.get('tool')} 的参数中未见租户上下文",
                        suggestion="确保所有数据操作都经过租户隔离",
                    ))

        result.dimensions["security"] = (
            AuditStatus.FAIL if issues_found else AuditStatus.PASS
        )

    async def _audit_code_quality(
        self, result: AuditResult, source_paths: list[str],
    ) -> None:
        """代码规范检查 (简版)"""
        import os

        issues_found = False
        for path in source_paths:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                # 检查: 文件末尾是否有换行
                if content and not content.endswith("\n"):
                    result.issues.append(AuditIssue(
                        dimension="code_quality",
                        severity=AuditStatus.WARN,
                        title=f"文件末尾缺少换行: {path}",
                        detail="PEP 8 要求文件以换行结尾",
                        suggestion="在文件末尾添加一个空行",
                    ))

                # 检查: TODO 标记
                if "TODO" in content:
                    todo_count = content.count("TODO")
                    if todo_count > 3:
                        result.issues.append(AuditIssue(
                            dimension="code_quality",
                            severity=AuditStatus.WARN,
                            title=f"{path} 中有 {todo_count} 个 TODO",
                            detail="大量未完成的 TODO",
                            suggestion="请在交付前处理或跟踪这些 TODO",
                        ))
                        issues_found = True

            except Exception:
                pass

        result.dimensions["code_quality"] = (
            AuditStatus.WARN if issues_found else AuditStatus.PASS
        )

    # ============================================================
    # 辅助
    # ============================================================

    def _calculate_score(self, result: AuditResult) -> float:
        """计算综合评分 (0.0-1.0)"""
        weights = {
            "completeness": 0.25,
            "step_trace": 0.25,
            "error_check": 0.20,
            "output_quality": 0.15,
            "security": 0.10,
            "code_quality": 0.05,
        }

        score = 0.0
        total_weight = 0.0

        for dim, weight in weights.items():
            status = result.dimensions.get(dim)
            if status is None or status == AuditStatus.SKIPPED:
                continue
            total_weight += weight
            if status == AuditStatus.PASS:
                score += weight
            elif status == AuditStatus.WARN:
                score += weight * 0.5
            # FAIL → 0

        return score / total_weight if total_weight > 0 else 1.0


# ============================================================
# 全局单例
# ============================================================

auditor = DeliveryAuditor()


# ============================================================
# 交付阻塞异常
# ============================================================

class DeliveryBlockedException(Exception):
    """审计未通过，阻塞交付"""

    def __init__(self, audit_result: AuditResult):
        self.audit_result = audit_result
        super().__init__(audit_result.summary)
