"""
daily_briefing Skill — 每日运营简报
"""

from app.modules.skill.registry import skill_registry
from .handler import daily_briefing


@skill_registry.register(
    name="daily_briefing",
    display_name="每日运营简报",
    description="自动汇总社群数据、保鲜预警、活动建议，生成今日运营简报。每天早上自动执行。也可以手动触发。",
    parameters_schema={},
    timeout=30,
    required_permissions=["agent:execute"],
    is_builtin=True,
)
async def daily_briefing_handler(params: dict, context: dict) -> dict:
    """生成每日运营简报。params 可为空，tenant_id 从 context 自动获取。"""
    tenant_id = str(context.get("tenant_id", ""))
    if not tenant_id:
        return {"error": "缺少租户上下文"}
    return await daily_briefing(tenant_id=tenant_id)
