"""知识库模块测试"""

import tempfile
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient


@pytest.fixture
async def auth(client: AsyncClient) -> dict:
    """创建知识库测试租户"""
    import uuid
    resp = await client.post("/api/v1/auth/register", json={
        "tenant_name": "KB Test Corp",
        "tenant_slug": f"kb-test-corp-{uuid.uuid4().hex[:8]}",
        "username": "kb_admin",
        "password": "admin123456",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_category(client: AsyncClient, auth: dict):
    """创建知识分类"""
    resp = await client.post("/api/v1/knowledge/categories", data={
        "name": "产品文档",
        "description": "产品相关文档",
        "color": "#FF5733",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "产品文档"


@pytest.mark.asyncio
async def test_list_categories(client: AsyncClient, auth: dict):
    """分类列表"""
    await client.post("/api/v1/knowledge/categories", data={"name": "Cat A"}, headers=auth)
    await client.post("/api/v1/knowledge/categories", data={"name": "Cat B"}, headers=auth)

    resp = await client.get("/api/v1/knowledge/categories", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_create_tag(client: AsyncClient, auth: dict):
    """创建标签"""
    resp = await client.post("/api/v1/knowledge/tags", data={"name": "API"}, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "API"


@pytest.mark.asyncio
async def test_duplicate_tag_rejected(client: AsyncClient, auth: dict):
    """重复标签被拒绝"""
    await client.post("/api/v1/knowledge/tags", data={"name": "DuplicateTag"}, headers=auth)
    resp = await client.post("/api/v1/knowledge/tags", data={"name": "DuplicateTag"}, headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_upload_txt_document(client: AsyncClient, auth: dict):
    """上传 TXT 文档"""
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("OPC 平台是一个集人员社交、管理、运营、交易于一体的移动端平台。\n\n"
                "它支持多租户数据隔离、内置知识库 RAG 问答、多智能体架构以及 Skill 系统。\n\n"
                "技术栈包括: Python FastAPI、PostgreSQL + pgvector、Redis、Celery。")
        tmp_path = f.name

    try:
        with open(tmp_path, "rb") as f:
            resp = await client.post("/api/v1/knowledge/upload", files={
                "file": ("test.txt", f, "text/plain"),
            }, data={
                "title": "OPC 平台介绍",
            }, headers=auth)

        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "OPC 平台介绍"
        assert data["file_type"] == "txt"
        assert data["status"] in ("processing", "ready")
        assert data["chunk_count"] > 0
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_list_documents(client: AsyncClient, auth: dict):
    """文档列表"""
    resp = await client.get("/api/v1/knowledge/documents", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data


@pytest.mark.asyncio
async def test_delete_document(client: AsyncClient, auth: dict):
    """删除文档"""
    # 先上传
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Test document content for deletion")
        tmp_path = f.name

    try:
        with open(tmp_path, "rb") as f:
            upload_resp = await client.post("/api/v1/knowledge/upload", files={
                "file": ("to_delete.txt", f, "text/plain"),
            }, data={"title": "待删除文档"}, headers=auth)
        doc_id = upload_resp.json()["id"]

        # 删除
        resp = await client.delete(f"/api/v1/knowledge/documents/{doc_id}", headers=auth)
        assert resp.status_code == 204

        # 确认已删除 (列表里不应该有)
        list_resp = await client.get("/api/v1/knowledge/documents", headers=auth)
        titles = [d["title"] for d in list_resp.json()["items"]]
        assert "待删除文档" not in titles
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_stats_endpoint(client: AsyncClient, auth: dict):
    """统计端点"""
    resp = await client.get("/api/v1/knowledge/stats", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "document_count" in data
    assert "chunk_count" in data
    assert "total_size_bytes" in data


@pytest.mark.asyncio
async def test_ask_without_documents(client: AsyncClient, auth: dict):
    """无文档时提问应返回友好提示"""
    resp = await client.post("/api/v1/knowledge/ask", data={
        "question": "OPC 平台是什么？",
        "top_k": 3,
    }, headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "sources" in data


@pytest.mark.asyncio
async def test_fulltext_search(client: AsyncClient, auth: dict):
    """全文搜索文档"""
    resp = await client.get("/api/v1/knowledge/search", params={"q": "OPC"}, headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
