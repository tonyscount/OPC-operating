"""
Skill 错误分类系统

Agent 编排质量取决于 Skill 的可靠性。标准化错误类型让 Agent 能智能决策:
  - PARAM_ERROR       → 修正参数后重试 1 次
  - PERMISSION_DENIED → 告知用户所需权限，不重试
  - EXTERNAL_API_FAIL → 换备用 API 或降级
  - INTERNAL_ERROR    → 记录日志，通知开发者
  - TIMEOUT           → 指数退避重试，最多 3 次
  - DATA_NOT_FOUND    → 告知用户无数据，建议换条件
"""

from enum import Enum
from typing import Any


class SkillErrorType(str, Enum):
    PARAM_ERROR = "param_error"
    PERMISSION_DENIED = "permission_denied"
    EXTERNAL_API_FAIL = "external_api_fail"
    INTERNAL_ERROR = "internal_error"
    TIMEOUT = "timeout"
    DATA_NOT_FOUND = "data_not_found"


class SkillError(Exception):
    """标准化 Skill 异常，Agent 可据此决策"""

    def __init__(
        self,
        error_type: SkillErrorType,
        message: str,
        skill_name: str = "",
        detail: Any = None,
        retry_allowed: bool = False,
    ):
        self.error_type = error_type
        self.message = message
        self.skill_name = skill_name
        self.detail = detail
        self.retry_allowed = retry_allowed
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "error": self.message,
            "type": self.error_type.value,
            "skill": self.skill_name,
            "retry_allowed": self.retry_allowed,
            "detail": str(self.detail)[:200] if self.detail else None,
        }

    @classmethod
    def from_exception(cls, exc: Exception, skill_name: str = "") -> "SkillError":
        """从原始异常推断错误类型"""
        msg = str(exc)
        msg_lower = msg.lower()

        if isinstance(exc, cls):
            return exc

        # 超时
        if any(k in msg_lower for k in ("timeout", "timed out", "connect timeout")):
            return cls(SkillErrorType.TIMEOUT, f"调用超时: {msg}", skill_name, exc, retry_allowed=True)

        # 权限
        if any(k in msg_lower for k in ("permission", "forbidden", "unauthorized", "401", "403")):
            return cls(SkillErrorType.PERMISSION_DENIED, f"权限不足: {msg}", skill_name, exc)

        # 外部 API
        if any(k in msg_lower for k in ("api", "http", "httpx", "connection", "dns", "resolve")):
            return cls(SkillErrorType.EXTERNAL_API_FAIL, f"外部服务不可用: {msg}", skill_name, exc, retry_allowed=True)

        # 参数
        if any(k in msg_lower for k in ("param", "argument", "missing", "required", "invalid", "type")):
            return cls(SkillErrorType.PARAM_ERROR, f"参数错误: {msg}", skill_name, exc, retry_allowed=True)

        # 数据不存在
        if any(k in msg_lower for k in ("not found", "no result", "no data", "empty")):
            return cls(SkillErrorType.DATA_NOT_FOUND, f"数据未找到: {msg}", skill_name, exc)

        # 默认内部错误
        return cls(SkillErrorType.INTERNAL_ERROR, f"内部错误: {msg}", skill_name, exc)


# Agent 决策表: 错误类型 → 策略
ERROR_STRATEGY = {
    SkillErrorType.PARAM_ERROR: {
        "max_retries": 1,
        "action": "analyze_and_fix_params",
        "description": "检查参数后重试 1 次",
    },
    SkillErrorType.PERMISSION_DENIED: {
        "max_retries": 0,
        "action": "inform_user",
        "description": "告知用户所需权限",
    },
    SkillErrorType.EXTERNAL_API_FAIL: {
        "max_retries": 2,
        "action": "switch_to_fallback",
        "description": "指数退避重试, 或切换备用 API",
    },
    SkillErrorType.INTERNAL_ERROR: {
        "max_retries": 0,
        "action": "log_and_notify",
        "description": "记录日志, 通知开发者",
    },
    SkillErrorType.TIMEOUT: {
        "max_retries": 3,
        "action": "exponential_backoff",
        "description": "指数退避重试, 最多 3 次",
    },
    SkillErrorType.DATA_NOT_FOUND: {
        "max_retries": 0,
        "action": "suggest_alternative",
        "description": "告知无数据, 建议换条件",
    },
}
