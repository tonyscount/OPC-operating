"""
event_planner Skill — 活动策划方案生成
"""

from app.modules.skill.registry import skill_registry
from .handler import event_planner


@skill_registry.register(
    name="event_planner",
    display_name="活动策划",
    description="基于社群真实数据和历史活动复盘，自动生成包含时间线、预算、分工、风险提示的结构化活动策划方案。用于策划线上线下活动。",
    parameters_schema={
        "event_type": {
            "type": "string",
            "description": "活动类型：线下聚会/线上分享/户外运动/聚餐/workshop/飞盘/读书会",
            "required": True,
        },
        "target_size": {
            "type": "integer",
            "description": "预期参与人数",
            "default": 20,
        },
        "budget": {
            "type": "integer",
            "description": "预算（元）",
            "default": 500,
        },
        "date_preference": {
            "type": "string",
            "description": "时间偏好：周末/工作日晚上/周五晚/任意",
            "default": "周末",
        },
    },
    timeout=45,
    required_permissions=["agent:execute"],
    is_builtin=True,
)
async def event_planner_handler(params: dict, context: dict) -> dict:
    """
    活动策划 Skill。组合调用 data_query + 知识库 + LLM。

    params: { event_type, target_size?, budget?, date_preference? }
    context: { user_id, tenant_id, trace_id }
    """
    return await event_planner(
        event_type=params.get("event_type", "线下聚会"),
        target_size=int(params.get("target_size", 20)),
        budget=int(params.get("budget", 500)),
        date_preference=params.get("date_preference", "周末"),
        tenant_id=str(context.get("tenant_id", "")),
        user_id=str(context.get("user_id", "")),
    )
