"""
Skill 注册表 — 装饰器注册 + 自动发现。

用法:
    from app.modules.skill.registry import skill_registry

    @skill_registry.register(
        name="search_knowledge",
        display_name="搜索知识库",
        description="在知识库中搜索相关文档内容",
        parameters_schema={
            "query": {"type": "string", "description": "搜索关键词"},
            "top_k": {"type": "integer", "description": "返回条数", "default": 5},
        },
        timeout=30,
        required_permissions=["knowledge:read"],
    )
    async def search_knowledge(params, context):
        ...
"""

import importlib
import inspect
import logging
import os
import pkgutil
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("opc.skill.registry")


class SkillRegistry:
    """
    全局 Skill 注册中心。

    - 装饰器注册: @skill_registry.register(...)
    - 自动发现: await skill_registry.auto_discover("skills/")
    - Agent 发现: skill_registry.list_skills() → LLM 选择调用
    """

    def __init__(self):
        self._skills: dict[str, dict] = {}  # name → skill_definition

    def register(
        self,
        *,
        name: str,
        display_name: str,
        description: str,
        parameters_schema: dict | None = None,
        timeout: int = 30,
        max_retries: int = 0,
        required_permissions: list[str] | None = None,
        is_builtin: bool = False,
    ) -> Callable:
        """
        装饰器: 注册一个 Skill。

        被装饰的函数将作为 Skill 的 handler。
        """
        def decorator(func: Callable):
            self._skills[name] = {
                "name": name,
                "display_name": display_name,
                "description": description,
                "parameters_schema": parameters_schema or {},
                "handler": func,
                "timeout": timeout,
                "max_retries": max_retries,
                "required_permissions": required_permissions or [],
                "is_builtin": is_builtin,
                "registered_from": f"{func.__module__}.{func.__name__}",
            }
            logger.info(f"Skill registered: {name} ← {func.__module__}.{func.__name__}")
            return func
        return decorator

    def get(self, name: str) -> dict | None:
        """获取 Skill 定义"""
        return self._skills.get(name)

    def list_skills(self, include_disabled: bool = False) -> list[dict]:
        """
        列出所有可用 Skill (供 Agent 发现)。

        返回给 LLM 的描述格式:
            { "name": "search_knowledge", "description": "...", "parameters": {...} }
        """
        skills = []
        for name, skill in self._skills.items():
            skills.append({
                "name": skill["name"],
                "display_name": skill["display_name"],
                "description": skill["description"],
                "parameters": skill["parameters_schema"],
                "required_permissions": skill["required_permissions"],
            })
        return skills

    def list_skills_for_llm(self) -> str:
        """
        生成给 LLM 的 Skill 列表文本 (用于 System Prompt)。
        """
        lines = ["## 可用工具/Skills\n"]
        for name, skill in self._skills.items():
            params_desc = ", ".join(
                f"{k}: {v.get('type', 'string')}" + ("?" if not v.get("required", True) else "")
                for k, v in skill["parameters_schema"].items()
            )
            lines.append(
                f"- **{skill['name']}**: {skill['description']}\n"
                f"  参数: ({params_desc})"
            )
        return "\n".join(lines)

    async def auto_discover(self, skills_dir: str | Path) -> int:
        """
        自动扫描 skills 目录，导入所有 Python 模块。
        模块中的 @skill_registry.register 装饰器会自动注册。

        返回: 发现的 Skill 数量
        """
        skills_path = Path(skills_dir)
        if not skills_path.exists():
            logger.warning(f"Skills directory not found: {skills_dir}")
            return 0

        before_count = len(self._skills)

        # 遍历 skills 目录下的所有 .py 文件
        for finder, name, ispkg in pkgutil.iter_modules([str(skills_path)]):
            if name.startswith("_"):
                continue
            try:
                importlib.import_module(f"skills.{name}")
                logger.info(f"Auto-discovered skill module: {name}")
            except Exception as e:
                logger.error(f"Failed to load skill module '{name}': {e}")

        new_count = len(self._skills) - before_count
        logger.info(f"Auto-discovery complete: {new_count} new skills loaded")
        return new_count

    def clear(self):
        """清空注册表 (测试用)"""
        self._skills.clear()

    @property
    def count(self) -> int:
        return len(self._skills)


# ========== 全局单例 ==========
skill_registry = SkillRegistry()
