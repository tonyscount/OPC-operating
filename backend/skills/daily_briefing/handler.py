"""
daily_briefing Skill — 每日运营简报

调用: data_query + 保鲜检查 → LLM 生成结构化简报
Celery Beat: 每天 8:00 自动执行
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger("opc.skill.daily_briefing")


async def daily_briefing(tenant_id: str) -> dict:
    """生成每日运营简报。由 Celery 定时触发或手动调用。"""

    data = {}
    expiring_count = 0

    # === Step 1: 社群数据 ===
    try:
        from skills.data_query.handler import data_query
        overview = await data_query("overview", tenant_id=tenant_id)
        new_members = await data_query("new_members", tenant_id=tenant_id, time_range="1d")
        engagement = await data_query("engagement", tenant_id=tenant_id, time_range="7d")
        popular = await data_query("popular_posts", tenant_id=tenant_id, time_range="7d")
        data["overview"] = overview
        data["new_members_today"] = new_members
        data["engagement_7d"] = engagement
        data["popular_7d"] = popular
    except Exception as e:
        logger.error(f"data_query failed: {e}")

    # === Step 2: 保鲜预警 ===
    try:
        from app.core.database import async_session_factory
        from sqlalchemy import select, func, or_
        from app.modules.knowledge.models import KnowledgeDocument
        from uuid import UUID

        async with async_session_factory() as db:
            expiring_count = await db.scalar(
                select(func.count(KnowledgeDocument.id)).where(
                    KnowledgeDocument.tenant_id == UUID(tenant_id),
                    KnowledgeDocument.is_deleted == False,
                    or_(
                        KnowledgeDocument.freshness == "expiring_soon",
                        KnowledgeDocument.freshness == "outdated",
                    ),
                )
            ) or 0
    except Exception as e:
        logger.error(f"Freshness check failed: {e}")

    # === Step 3: LLM 生成简报 ===
    prompt = f"""你是 OPC 社群运营助手。根据以下真实数据生成一份"今日运营简报"。

## 社群数据
- 总览: {data.get('overview', {}).get('detail', '无数据')}
- 昨日新增成员: {data.get('new_members_today', {}).get('detail', '无数据')}
- 7天互动率: {data.get('engagement_7d', {}).get('detail', '无数据')}
- 7天热门帖子: {data.get('popular_7d', {}).get('detail', '无数据')}

## 保鲜状态
- 待处理过期文档: {expiring_count} 份

## 输出格式 (纯文本，不要 markdown 代码块)
📊 今日数据
· 成员总数 X，昨日新增 Y
· 7 日互动率 Z%

⚠️ 需要关注
· (如果有过期文档) X 份文档待保鲜
· (如果互动率低于30%) 互动率偏低
· (如果有异常数据) 标注异常

💡 建议行动
· 具体可执行的建议 (基于数据)

🌟 一句话激励
· 给主理人的正能量"""

    briefing_text = await _call_llm(prompt)

    return {
        "briefing": briefing_text,
        "data_snapshot": {
            "members": data.get("overview", {}).get("members"),
            "new_today": data.get("new_members_today", {}).get("value"),
            "engagement": data.get("engagement_7d", {}).get("value"),
            "expiring_docs": expiring_count,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _call_llm(prompt: str) -> str:
    """调用 LLM 生成简报文本"""
    from app.config import settings

    if not settings.OPENAI_API_KEY or len(settings.OPENAI_API_KEY) < 20:
        return """📊 今日数据
· 成员总数: 2，昨日新增: 0
· 7 日互动率: 50%

⚠️ 需要关注
· API Key 未配置，简报为静态模板

💡 建议行动
· 在 ⚙️ 设置中配置 DeepSeek API Key 以获取定制简报

🌟 每天前进一小步，积累就是一大步。"""

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            timeout=30.0,
        )
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是社群运营数据分析师。只返回简报文本，不要任何前缀。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=800,
        )
        return response.choices[0].message.content or "(生成失败)"
    except Exception as e:
        logger.error(f"LLM briefing failed: {e}")
        return f"(简报生成失败: {e})"
