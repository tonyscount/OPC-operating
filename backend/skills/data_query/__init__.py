"""
data_query Skill — 查询社群内部运营数据
"""

from app.modules.skill.registry import skill_registry
from .handler import data_query


@skill_registry.register(
    name="data_query",
    display_name="社群数据查询",
    description="查询社群内部运营数据，包括成员统计、帖子分析、活跃度趋势。当用户询问社群运营数据、增长情况、活跃度时使用。",
    parameters_schema={
        "metric": {
            "type": "string",
            "description": "查询指标: member_count(成员总数) / new_members(新增成员) / popular_posts(热门帖子) / engagement(互动率) / overview(综合概览)",
            "enum": ["member_count", "new_members", "popular_posts", "engagement", "overview"],
            "required": True,
        },
        "time_range": {
            "type": "string",
            "description": "时间范围: 7d / 30d / 90d",
            "default": "7d",
        },
    },
    timeout=10,
    required_permissions=["agent:execute"],
    is_builtin=True,
)
async def data_query_handler(params: dict, context: dict) -> dict:
    """
    查询社群内部数据。

    params: { metric, time_range }
    context: { user_id, tenant_id, trace_id }
    """
    metric = params.get("metric", "overview")
    time_range = params.get("time_range", "7d")
    tenant_id = context.get("tenant_id", "")

    if not tenant_id:
        return {"error": "缺少租户上下文", "metric": metric}

    return await data_query(
        metric=metric,
        tenant_id=str(tenant_id),
        time_range=time_range,
    )
