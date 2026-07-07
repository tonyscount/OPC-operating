"""
web_search Skill — 注册到 OPC Skill 系统
"""

from app.modules.skill.registry import skill_registry
from .handler import web_search


@skill_registry.register(
    name="web_search",
    display_name="网络搜索",
    description="搜索互联网获取外部最新信息。当用户询问最新资讯、行业趋势、实时数据等内部知识库无法回答的问题时使用。",
    parameters_schema={
        "query": {
            "type": "string",
            "description": "搜索关键词",
            "required": True,
        },
        "max_results": {
            "type": "integer",
            "description": "最大返回结果数",
            "default": 5,
        },
    },
    timeout=15,
    required_permissions=["agent:execute"],
    is_builtin=True,
)
async def web_search_handler(params: dict, context: dict) -> dict:
    """
    执行网络搜索。

    params: { query: str, max_results?: int }
    context: { user_id, tenant_id, trace_id }
    """
    query = params.get("query", "")
    max_results = min(int(params.get("max_results", 5)), 10)

    if not query:
        return {"error": "缺少搜索关键词", "results": [], "total": 0}

    return await web_search(query=query, max_results=max_results)
