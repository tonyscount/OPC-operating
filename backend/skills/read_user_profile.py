"""
Skill: 读取用户资料

Agent 调用此 Skill 获取指定用户的公开资料信息。
"""

from app.modules.skill.registry import skill_registry


@skill_registry.register(
    name="read_user_profile",
    display_name="读取用户资料",
    description="获取指定用户的公开资料，包括用户名、显示名、头像和社交统计",
    parameters_schema={
        "user_id": {
            "type": "string",
            "description": "要查询的用户 ID",
            "required": True,
        },
    },
    timeout=10,
    required_permissions=["user:read"],
    is_builtin=True,
)
async def read_user_profile(params: dict, context: dict) -> dict:
    """
    获取用户公开资料。

    context: { user_id, tenant_id, trace_id }
    """
    from uuid import UUID
    from app.core.database import async_session_factory
    from app.modules.user.service import get_profile

    target_user_id = params.get("user_id")
    tenant_id = context.get("tenant_id")

    async with async_session_factory() as db:
        profile = await get_profile(
            db,
            tenant_id=UUID(tenant_id) if tenant_id else None,
            user_id=UUID(target_user_id),
        )

    # 只返回公开信息，脱敏处理
    return {
        "username": profile.get("username"),
        "display_name": profile.get("display_name"),
        "avatar_url": profile.get("avatar_url"),
        "stats": profile.get("stats", {}),
    }
