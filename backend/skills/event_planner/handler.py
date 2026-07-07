"""
event_planner Skill — 活动策划方案生成 (含 MUSE 技能记忆)

组合调用: data_query (社群数据) + 知识库 (历史复盘) + LLM (方案生成)
每次执行后自动写入 .memory.md，下次执行时读取经验。
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("opc.skill.event_planner")

MEMORY_FILE = Path(__file__).parent / ".memory.md"


def _read_memory() -> str:
    """读取技能记忆"""
    try:
        if MEMORY_FILE.exists():
            return MEMORY_FILE.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


def _write_memory(entry: str):
    """追加技能记忆"""
    try:
        existing = _read_memory()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        new_entry = f"\n## {timestamp}\n{entry}\n"
        MEMORY_FILE.write_text(existing + new_entry, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to write memory: {e}")

logger = logging.getLogger("opc.skill.event_planner")


async def event_planner(
    event_type: str,
    tenant_id: str,
    user_id: str,
    target_size: int = 20,
    budget: int = 500,
    date_preference: str = "周末",
) -> dict:
    """
    生成结构化的活动策划方案。
    零外部 API 依赖 — LLM 调用复用 DeepSeek/OpenAI 配置。
    """
    insights = {}
    history_context = ""
    members = 0

    # === Step 1: 查社群数据 (内调 data_query handler) ===
    try:
        from skills.data_query.handler import data_query
        overview = await data_query("overview", tenant_id=tenant_id)
        new_members = await data_query("new_members", tenant_id=tenant_id, time_range="30d")
        engagement = await data_query("engagement", tenant_id=tenant_id, time_range="30d")
        insights["overview"] = overview
        insights["new_members"] = new_members
        insights["engagement"] = engagement
        members = overview.get("members", target_size)
        logger.info(f"Data queried: {members} members, engagement={engagement.get('value')}%")
    except Exception as e:
        logger.warning(f"data_query failed: {e}")
        insights["error"] = str(e)

    # === Step 2: 查历史活动复盘 (内调知识库) ===
    try:
        from app.modules.knowledge.vector_store import vector_store
        from app.modules.knowledge.embedding import get_embedding_service

        emb = get_embedding_service()
        if emb.is_available:
            query_vec = await emb.embed_query(f"{event_type} 活动复盘 经验总结")
            results = vector_store.search(
                tenant_id=str(tenant_id),
                query_embedding=query_vec,
                top_k=3,
            )
            if results:
                history_parts = [f"- {r.get('document_title', '')}: {r.get('content', '')[:200]}" for r in results]
                history_context = "\n".join(history_parts)
                logger.info(f"Found {len(results)} history documents")
        else:
            history_context = ""
    except Exception as e:
        logger.warning(f"Knowledge search failed: {e}")

    # === Step 3: 组装 Prompt (含技能记忆)，调 LLM 生成 ===
    memory = _read_memory()
    memory_section = ""
    if memory:
        memory_section = f"\n## 往期策划经验（技能记忆）\n{memory[-2000:]}\n"

    prompt = f"""你是 OPC 社群的运营专家。请根据以下真实数据，策划一场活动方案。

## 活动要求
- 类型：{event_type}
- 预期人数：{target_size}人
- 预算：{budget}元
- 时间偏好：{date_preference}

## 社群数据洞察
- 总成员：{members}人
- 互动率：{insights.get('engagement', {}).get('detail', '未知')}
- 新增成员：{insights.get('new_members', {}).get('detail', '未知')}
{memory_section}
## 往期活动参考
{history_context if history_context else '暂无往期活动记录（这是首次该类型活动）'}

## 输出要求
返回纯 JSON（不要 markdown 代码块包裹，不要 ```json）：
{{
  "title": "活动标题（吸引人、10字以内）",
  "brief": "一句话介绍（20字以内）",
  "timeline": [
    {{"phase": "活动前3天", "action": "发布预告海报"}},
    {{"phase": "活动当天14:00", "action": "场地布置签到"}},
    {{"phase": "活动当天15:00", "action": "正式开始"}}
  ],
  "budget_breakdown": [
    {{"item": "场地", "amount": 200}},
    {{"item": "物料", "amount": 100}}
  ],
  "task_assignment": [
    {{"role": "主持人", "person_count": 1, "duty": "控场破冰"}},
    {{"role": "摄影师", "person_count": 1, "duty": "拍照记录"}}
  ],
  "risk_notes": ["雨天备选", "人数不足延期"],
  "promotion_text": "社群公告文案，80字以内"
}}

预算总和必须等于 {budget} 元。"""

    plan = await _call_llm(prompt)

    # 写入技能记忆 (MUSE: 每次执行后学习)
    if not plan.get("error"):
        memory_entry = (
            f"- 活动类型: {event_type}\n"
            f"- 社群规模: {members}人, 互动率: {insights.get('engagement', {}).get('value', '?')}%\n"
            f"- 预算: {budget}元, 人数: {target_size}人\n"
            f"- 生成方案: {plan.get('title', 'N/A')}\n"
            f"- 关键建议: {plan.get('brief', '')}\n"
        )
        _write_memory(memory_entry)
    else:
        _write_memory(f"- 执行失败: {plan.get('error', 'unknown')}\n")

    return {
        "plan": plan,
        "data_insights": {
            "members": members,
            "engagement": insights.get("engagement", {}).get("value"),
            "new_members_30d": insights.get("new_members", {}).get("value"),
        },
        "history_reference": history_context if history_context else "这是该类型首次活动，无往期参考",
        "has_memory": bool(_read_memory()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _call_llm(prompt: str) -> dict:
    """调用 LLM 生成方案 JSON"""
    from app.config import settings

    if not settings.OPENAI_API_KEY or len(settings.OPENAI_API_KEY) < 20:
        return {
            "error": "LLM 未配置",
            "title": f"线下聚会策划方案 (模板)",
            "brief": "请在设置中配置 API Key 以生成定制方案",
            "timeline": [
                {"phase": "活动前7天", "action": "确定主题和场地"},
                {"phase": "活动前3天", "action": "发布公告收集报名"},
                {"phase": "活动前1天", "action": "确认人数和物料"},
                {"phase": "活动当天", "action": "签到→活动→自由交流"},
            ],
            "budget_breakdown": [
                {"item": "场地", "amount": 200},
                {"item": "物料", "amount": 100},
                {"item": "茶歇", "amount": 150},
                {"item": "备用", "amount": 50},
            ],
            "task_assignment": [
                {"role": "主持人", "person_count": 1, "duty": "流程控制和破冰引导"},
                {"role": "签到员", "person_count": 1, "duty": "签到和物料发放"},
                {"role": "摄影师", "person_count": 1, "duty": "活动拍照记录"},
            ],
            "risk_notes": ["雨天备选室内方案", "人数少于10人则延期", "提前确认场地设备"],
            "promotion_text": "本周活动来啦！一起交流学习，名额有限先到先得。",
            "note": "以上为模板方案。配置 DeepSeek/OpenAI API Key 后可生成定制方案。",
        }

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
                {"role": "system", "content": "你是活动策划专家。只返回 JSON，不要任何解释或 markdown。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
        )
        text = response.choices[0].message.content or "{}"

        # 清理可能的 markdown 包裹
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]

        return json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {"error": "JSON 解析失败", "raw": text[:500]}
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return {"error": f"LLM 调用失败: {str(e)}"}
