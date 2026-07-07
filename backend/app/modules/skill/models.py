"""
Skill 系统数据模型

Skill 可以从数据库加载，也可以通过 @skill_registry.register 装饰器代码注册。
数据库模型用于管理后台的 CRUD 操作。
"""

import uuid

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import TenantBase


class SkillDefinition(TenantBase):
    """
    Skill 定义表。

    每个 Skill 是一个可以被 Agent 调用的工具/API。
    """
    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(
        String(200), unique=True, nullable=False, comment="Skill 唯一标识"
    )
    display_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="显示名称"
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, comment="自然语言描述 (Agent 选择 Skill 时参考)"
    )
    parameters_schema: Mapped[dict] = mapped_column(
        JSONB, default=dict, comment="参数 JSON Schema"
    )
    handler_module: Mapped[str] = mapped_column(
        String(500), nullable=True, comment="执行函数所在模块路径"
    )
    handler_function: Mapped[str] = mapped_column(
        String(200), nullable=True, comment="执行函数名"
    )
    timeout: Mapped[int] = mapped_column(
        Integer, default=30, comment="超时秒数"
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, default=0, comment="最大重试次数"
    )
    required_permissions: Mapped[list[str]] = mapped_column(
        JSONB, default=list, comment="所需权限标识列表"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否启用"
    )
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否内置 Skill (不可删除)"
    )
    version: Mapped[str] = mapped_column(
        String(20), default="1.0.0", comment="Skill 版本"
    )
