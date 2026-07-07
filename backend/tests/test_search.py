"""搜索模块测试"""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def auth(client: AsyncClient) -> dict:
    """创建搜索测试环境"""
    resp = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Search Test",
        "tenant_slug": "search-test",
        "username": "searcher",
        "password": "pass123456",
    })
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers


@pytest.mark.asyncio
async def test_search_no_results(client: AsyncClient, auth: dict):
    """无结果搜索"""
    resp = await client.post("/api/v1/search", json={
        "query": "xyz不存在的搜索词abc",
        "page": 1,
        "page_size": 20,
    }, headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0
    assert data["has_more"] == False


@pytest.mark.asyncio
async def test_search_status(client: AsyncClient, auth: dict):
    """查看搜索模式"""
    resp = await client.get("/api/v1/search/status", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] in ("mock", "external")


@pytest.mark.asyncio
async def test_search_pagination(client: AsyncClient, auth: dict):
    """分页验证"""
    resp = await client.post("/api/v1/search", json={
        "query": "test",
        "page": 1,
        "page_size": 5,
    }, headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert "has_more" in data


@pytest.mark.asyncio
async def test_search_unauthorized(client: AsyncClient):
    """未登录不能搜索"""
    resp = await client.post("/api/v1/search", json={
        "query": "test",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_empty_query_rejected(client: AsyncClient, auth: dict):
    """空查询被拒绝"""
    resp = await client.post("/api/v1/search", json={
        "query": "",
    }, headers=auth)
    assert resp.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_search_with_filters(client: AsyncClient, auth: dict):
    """带筛选条件的搜索"""
    resp = await client.post("/api/v1/search", json={
        "query": "test",
        "filters": {"source_type": "knowledge"},
        "sort": "date",
    }, headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "test"


@pytest.mark.asyncio
async def test_search_suggest(client: AsyncClient, auth: dict):
    """搜索建议"""
    resp = await client.get("/api/v1/search/suggest", params={"q": "OPC"}, headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "suggestions" in data
