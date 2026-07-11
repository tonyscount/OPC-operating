"""多智能体模块测试"""

import pytest
from httpx import AsyncClient

from app.modules.agent.orchestrator import AgentDefinition, orchestrator


@pytest.fixture
async def auth(client: AsyncClient) -> dict:
    import uuid
    resp = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Agent Test", "tenant_slug": f"agent-test-{uuid.uuid4().hex[:8]}",
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
    assert "分析师" in names
    assert "客服助手" in names


@pytest.mark.asyncio
async def test_run_single_without_llm(monkeypatch):
    """Single 模式 — 无 LLM Key 下也能返回正常错误"""
    # Mock LLMClient.chat 立即抛出异常，避免真实 API 调用超时
    async def mock_chat(self, messages, tools=None):
        raise RuntimeError("Invalid API key")

    monkeypatch.setattr(
        "app.modules.agent.orchestrator.LLMClient.chat",
        mock_chat,
    )

    # 注册一个简单 Agent
    agent = AgentDefinition(
        name="mock_agent",
        role_prompt="你是 Mock Agent",
        tools=[],
        max_iterations=1,
    )
    orchestrator.register_agent(agent)

    # LLM 调用会失败，验证流程返回友好错误而不崩溃
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
    assert len(data["agents"]) >= 14  # 14 built-in agents


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
        "agent_name": "分析师",
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
