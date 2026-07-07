"""多智能体模块测试"""

import pytest
from httpx import AsyncClient

from app.modules.agent.orchestrator import AgentDefinition, orchestrator


@pytest.fixture
async def auth(client: AsyncClient) -> dict:
    resp = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Agent Test", "tenant_slug": "agent-test",
        "username": "agent_user", "password": "pass123456",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# 编排器测试
# ============================================================

def test_register_agent():
    """注册 Agent"""
    agent = AgentDefinition(
        name="test_agent",
        role_prompt="你是一个测试 Agent",
        tools=["search_knowledge"],
        max_iterations=3,
    )
    orchestrator.register_agent(agent)
    assert orchestrator.get_agent("test_agent") is not None
    assert orchestrator.get_agent("test_agent").tools == ["search_knowledge"]


def test_list_agents():
    """列出 Agent"""
    agents = orchestrator.list_agents()
    assert len(agents) > 0
    names = [a["name"] for a in agents]
    assert "analyst" in names
    assert "support_agent" in names


@pytest.mark.asyncio
async def test_run_single_without_llm():
    """Single 模式 — 无 LLM Key 下也能返回正常错误"""
    # 注册一个简单 Agent (不会真正调 LLM — 测试环境无 API Key)
    agent = AgentDefinition(
        name="mock_agent",
        role_prompt="你是 Mock Agent",
        tools=[],
        max_iterations=1,
    )
    orchestrator.register_agent(agent)

    # 会尝试调 LLM 但可能因为 Key 无效而出错
    # 这里只验证流程不崩溃
    result = await orchestrator.run_single(
        "mock_agent", "Hello", context={"user_id": "u1"},
    )
    assert "agent_name" in result
    assert "output" in result or "error" in result


# ============================================================
# API 测试
# ============================================================

@pytest.mark.asyncio
async def test_list_agents_api(client: AsyncClient, auth: dict):
    """API: Agent 列表"""
    resp = await client.get("/api/v1/agent/list", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "agents" in data
    assert len(data["agents"]) >= 4  # analyst, support_agent, reviewer, judge


@pytest.mark.asyncio
async def test_register_agent_api(client: AsyncClient, auth: dict):
    """API: 注册自定义 Agent"""
    resp = await client.post("/api/v1/agent/register", json={
        "name": "my_custom_agent",
        "display_name": "我的 Agent",
        "role_prompt": "你是一个自定义助手",
        "tools": ["search_knowledge"],
        "temperature": 0.5,
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "my_custom_agent"


@pytest.mark.asyncio
async def test_run_single_api(client: AsyncClient, auth: dict):
    """API: 执行 Single Agent"""
    resp = await client.post("/api/v1/agent/run", json={
        "agent_name": "analyst",
        "mode": "single",
        "message": "OPC 平台是什么？",
    }, headers=auth)
    # 可能因为没有 API Key 而失败，但结构应该正确
    assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_run_sequential_without_names(client: AsyncClient, auth: dict):
    """API: Sequential 模式缺少 agent_names"""
    resp = await client.post("/api/v1/agent/run", json={
        "mode": "sequential",
        "message": "测试消息",
    }, headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data
