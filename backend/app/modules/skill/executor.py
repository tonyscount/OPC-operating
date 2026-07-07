"""
Skill 执行引擎

职责:
  1. 参数校验 (JSON Schema 验证)
  2. 权限检查
  3. 超时控制 (asyncio.wait_for)
  4. 重试机制
  5. 日志记录 & 链路追踪
  6. 错误处理 & 统一返回格式
"""

import asyncio
import inspect
import logging
import time
import uuid
from typing import Any

from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.modules.skill.errors import SkillError, SkillErrorType, ERROR_STRATEGY
from app.modules.skill.registry import skill_registry

logger = logging.getLogger("opc.skill.executor")


class SkillExecutor:
    """Skill 执行引擎"""

    async def execute(
        self,
        skill_name: str,
        parameters: dict[str, Any],
        *,
        user_id: uuid.UUID | None = None,
        tenant_id: uuid.UUID | None = None,
        user_permissions: list[str] | None = None,
        trace_id: str | None = None,
    ) -> dict:
        """
        执行一个 Skill。

        返回:
            { "success": true, "skill_name": "...", "result": ..., "took_ms": ..., "trace_id": "..." }
        """
        trace_id = trace_id or str(uuid.uuid4())[:8]
        start = time.perf_counter()

        # 1. 查找 Skill
        skill = skill_registry.get(skill_name)
        if not skill:
            return self._error(skill_name, f"Skill '{skill_name}' 不存在", trace_id, start,
                             error_type=SkillErrorType.DATA_NOT_FOUND.value)

        # 2. 权限检查
        required = skill.get("required_permissions", [])
        if required and user_permissions is not None:
            if not self._check_permissions(required, user_permissions):
                return self._error(
                    skill_name,
                    f"权限不足，需要: {required}",
                    trace_id, start,
                    error_type=SkillErrorType.PERMISSION_DENIED.value,
                )

        # 3. 参数校验
        param_schema = skill.get("parameters_schema", {})
        if param_schema:
            try:
                parameters = self._validate_params(parameters, param_schema)
            except ValidationException as e:
                return self._error(skill_name, f"参数校验失败: {e.message}", trace_id, start,
                                 error_type=SkillErrorType.PARAM_ERROR.value, retry_allowed=True)

        # 4. 执行 (含超时 + 重试)
        handler = skill["handler"]
        timeout = skill.get("timeout", 30)
        max_retries = skill.get("max_retries", 0)

        context = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "trace_id": trace_id,
        }

        last_error = None
        skerr = None
        for attempt in range(max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self._call_handler(handler, parameters, context),
                    timeout=timeout,
                )

                took_ms = int((time.perf_counter() - start) * 1000)
                logger.info(
                    f"[{trace_id}] Skill '{skill_name}' executed successfully "
                    f"in {took_ms}ms (attempt {attempt + 1}/{max_retries + 1})"
                )

                return {
                    "success": True,
                    "skill_name": skill_name,
                    "result": result,
                    "took_ms": took_ms,
                    "trace_id": trace_id,
                    "attempts": attempt + 1,
                }

            except asyncio.TimeoutError:
                skerr = SkillError(SkillErrorType.TIMEOUT, f"执行超时 ({timeout}s)", skill_name, retry_allowed=True)
                last_error = skerr.message
                logger.warning(f"[{trace_id}] Skill '{skill_name}' timeout (attempt {attempt + 1})")

            except Exception as e:
                skerr = self._classify_error(e, skill_name)
                last_error = skerr.message
                logger.error(
                    f"[{trace_id}] Skill '{skill_name}' [{skerr.error_type.value}] {e} (attempt {attempt + 1})",
                )

            if attempt < max_retries and isinstance(skerr, SkillError) and skerr.retry_allowed:
                retry_delay = min(2 ** attempt, 10)  # 指数退避: 1s, 2s, 4s, 8s, 10s
                await asyncio.sleep(retry_delay)

        # 最终失败，返回分类错误
        if isinstance(skerr, SkillError):
            return self._error(skill_name, skerr.message, trace_id, start,
                             error_type=skerr.error_type.value, retry_allowed=skerr.retry_allowed)
        return self._error(skill_name, last_error or "执行失败", trace_id, start,
                         error_type=SkillErrorType.INTERNAL_ERROR.value)

    async def execute_batch(
        self,
        calls: list[dict],
        *,
        user_id: uuid.UUID | None = None,
        tenant_id: uuid.UUID | None = None,
        user_permissions: list[str] | None = None,
    ) -> list[dict]:
        """并发执行多个 Skill"""
        tasks = []
        for call in calls:
            tasks.append(
                self.execute(
                    skill_name=call["skill_name"],
                    parameters=call.get("parameters", {}),
                    user_id=user_id,
                    tenant_id=tenant_id,
                    user_permissions=user_permissions,
                    trace_id=call.get("trace_id"),
                )
            )
        return await asyncio.gather(*tasks)

    # ========== 内部方法 ==========

    async def _call_handler(self, handler, params: dict, context: dict) -> Any:
        """调用 handler 函数，支持同步/异步"""
        result = handler(params, context)
        if inspect.isawaitable(result):
            result = await result
        return result

    def _validate_params(self, params: dict, schema: dict) -> dict:
        """简单的参数校验 (不依赖 jsonschema 库)"""
        validated = dict(params)
        for key, field_schema in schema.items():
            # 必填检查
            if field_schema.get("required", False) and key not in params:
                raise ValidationException(f"缺少必填参数: {key}")
            # 类型检查
            if key in params:
                expected_type = field_schema.get("type", "string")
                if not self._check_type(params[key], expected_type):
                    raise ValidationException(f"参数 {key} 类型应为 {expected_type}")
            # 枚举检查
            if key in params and "enum" in field_schema:
                if params[key] not in field_schema["enum"]:
                    raise ValidationException(
                        f"参数 {key} 值应为 {field_schema['enum']} 之一"
                    )
            # 默认值
            if key not in params and "default" in field_schema:
                validated[key] = field_schema["default"]
        return validated

    def _check_type(self, value: Any, expected: str) -> bool:
        type_map = {
            "string": str, "integer": int, "number": (int, float),
            "boolean": bool, "array": list, "object": dict,
        }
        expected_type = type_map.get(expected)
        if expected_type is None:
            return True
        return isinstance(value, expected_type)

    def _check_permissions(self, required: list[str], granted: list[str]) -> bool:
        """检查是否拥有所需权限"""
        if not required:
            return True
        granted_set = set(granted)
        for perm in required:
            if perm in granted_set:
                return True
            # 通配符
            if "*" in granted_set or "*:*" in granted_set:
                return True
            parts = perm.split(":")
            for i in range(len(parts), 0, -1):
                if ":".join(parts[:i]) + ":*" in granted_set:
                    return True
        return False

    def _error(self, skill_name: str, message: str, trace_id: str, start: float,
               error_type: str = "", retry_allowed: bool = False) -> dict:
        took_ms = int((time.perf_counter() - start) * 1000)
        result = {
            "success": False,
            "skill_name": skill_name,
            "error": message,
            "error_type": error_type,
            "retry_allowed": retry_allowed,
            "took_ms": took_ms,
            "trace_id": trace_id,
        }
        if error_type and error_type in ERROR_STRATEGY:
            result["recovery_hint"] = ERROR_STRATEGY[error_type]["description"]
        return result

    def _classify_error(self, exc: Exception, skill_name: str) -> SkillError:
        """将原始异常分类为 SkillError"""
        return SkillError.from_exception(exc, skill_name)


# ========== 全局单例 ==========
executor = SkillExecutor()
