"""
交付审计 Hook 测试
"""

import pytest
from httpx import AsyncClient

from app.modules.agent.audit_hook import (
    AuditIssue,
    AuditResult,
    AuditStatus,
    DeliveryAuditor,
    DeliveryBlockedException,
    auditor,
)


@pytest.fixture
async def auth(client: AsyncClient) -> dict:
    resp = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Audit Test", "tenant_slug": "audit-test",
        "username": "audit_user", "password": "pass123456",
    })
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ============================================================
# 审计器核心测试
# ============================================================

@pytest.mark.asyncio
async def test_audit_all_pass():
    """所有维度通过"""
    auditor = DeliveryAuditor()
    auditor.set_requirements(["实现登录功能", "支持JWT"])
    auditor.set_steps(["创建User模型", "编写登录API", "添加测试"])

    result = await auditor.audit(
        output="已实现用户登录功能，使用JWT进行身份验证。包含User模型、登录API和完整测试。",
        steps_executed=["创建User模型", "编写登录API", "添加测试"],
        errors=[],
    )

    assert result.passed == True
    assert result.blocked == False
    assert result.score > 0.8
    assert "通过" in result.summary


@pytest.mark.asyncio
async def test_audit_missing_requirement():
    """缺失需求 → FAIL"""
    auditor = DeliveryAuditor()
    auditor.set_requirements(["用户登录", "支付功能", "消息推送"])

    result = await auditor.audit(
        output="实现了用户登录和JWT验证。",  # 缺少支付和推送
        steps_executed=["创建User模型"],
        errors=[],
    )

    assert result.passed == False
    assert result.blocked == True
    assert result.fail_count >= 2  # 支付 + 推送
    assert "支付功能" in str(result.issues) or any("支付" in i.title for i in result.issues)


@pytest.mark.asyncio
async def test_audit_skipped_step():
    """跳步 → FAIL"""
    auditor = DeliveryAuditor()
    auditor.set_steps(["需求分析", "数据库设计", "API开发", "测试", "部署"])

    result = await auditor.audit(
        output="完成了API开发",
        steps_executed=["API开发", "部署"],  # 跳过了需求分析和测试
        errors=[],
    )

    assert result.passed == False
    step_issues = [i for i in result.issues if i.dimension == "step_trace"]
    assert len(step_issues) >= 2  # 至少缺少需求分析和测试


@pytest.mark.asyncio
async def test_audit_execution_errors():
    """执行错误 → FAIL"""
    auditor = DeliveryAuditor()

    result = await auditor.audit(
        output="Some output",
        steps_executed=[],
        errors=["Database connection timeout", "API rate limit exceeded"],
    )

    assert result.passed == False
    error_issues = [i for i in result.issues if i.dimension == "error_check"]
    assert len(error_issues) >= 2


@pytest.mark.asyncio
async def test_audit_todo_in_output():
    """输出中有 TODO → FAIL"""
    auditor = DeliveryAuditor()

    result = await auditor.audit(
        output="功能基本完成，TODO: 添加错误处理，FIXME: 修复并发问题",
        steps_executed=[],
        errors=[],
    )

    assert result.passed == False
    todo_issues = [i for i in result.issues if i.dimension == "output_quality" and i.severity == AuditStatus.FAIL]
    assert len(todo_issues) >= 1


@pytest.mark.asyncio
async def test_audit_empty_output():
    """空输出 → FAIL"""
    auditor = DeliveryAuditor()

    result = await auditor.audit(
        output="",
        steps_executed=[],
        errors=[],
    )

    assert result.passed == False


@pytest.mark.asyncio
async def test_audit_api_key_leak():
    """输出中有密钥 → FAIL"""
    auditor = DeliveryAuditor()

    result = await auditor.audit(
        output="配置: OPENAI_API_KEY=sk-abc123xyz",
        steps_executed=[],
        errors=[],
    )

    security_issues = [i for i in result.issues if i.dimension == "security"]
    assert len(security_issues) >= 1


@pytest.mark.asyncio
async def test_audit_truncated_output():
    """截断输出 → WARN"""
    auditor = DeliveryAuditor()

    result = await auditor.audit(
        output="这是一个很长的分析结果，但是后面省略了...",
        steps_executed=[],
        errors=[],
    )

    # 截断是 WARN 不是 FAIL
    trunc_issues = [i for i in result.issues if i.dimension == "output_quality" and i.severity == AuditStatus.WARN]
    assert len(trunc_issues) >= 1
    # 可能有 WARN 但不一定 FAIL
    assert result.score < 1.0


@pytest.mark.asyncio
async def test_audit_score_calculation():
    """评分计算"""
    auditor = DeliveryAuditor()
    auditor.set_requirements(["A", "B", "C"])
    auditor.set_steps(["1", "2", "3"])

    # 全部完美
    result = await auditor.audit(
        output="A B C", steps_executed=["1", "2", "3"], errors=[],
    )
    assert result.score == 1.0

    # 只有 WARN
    result = await auditor.audit(
        output="A B ...", steps_executed=["1", "2", "3", "extra"], errors=[],
    )
    assert 0.5 <= result.score < 1.0  # WARN 会扣分但不会太低

    # 全部失败
    result = await auditor.audit(
        output="", steps_executed=[], errors=["fatal error"],
    )
    assert result.score < 0.5


# ============================================================
# API 测试
# ============================================================

@pytest.mark.asyncio
async def test_audit_api(client: AsyncClient, auth: dict):
    """POST /agent/audit"""
    resp = await client.post("/api/v1/agent/audit", json={
        "output": "实现了用户登录功能，支持JWT认证",
        "steps_executed": ["创建User模型", "编写登录API", "测试"],
        "requirements": ["用户登录", "JWT认证"],
        "errors": [],
    }, headers=auth)

    assert resp.status_code == 200
    data = resp.json()
    assert "passed" in data
    assert "score" in data
    assert "dimensions" in data
    assert "issues" in data


@pytest.mark.asyncio
async def test_audit_api_detect_issues(client: AsyncClient, auth: dict):
    """审计 API 检测到问题"""
    resp = await client.post("/api/v1/agent/audit", json={
        "output": "TODO: 完成支付模块",
        "steps_executed": ["API开发"],
        "requirements": ["用户登录", "支付功能", "消息推送"],
        "errors": ["外部API调用失败"],
    }, headers=auth)

    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] == False
    assert data["fail_count"] > 0


@pytest.mark.asyncio
async def test_audit_dimensions_api(client: AsyncClient, auth: dict):
    """GET /agent/audit/dimensions"""
    resp = await client.get("/api/v1/agent/audit/dimensions", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "dimensions" in data
    assert len(data["dimensions"]) == 6
    assert "completeness" in data["dimensions"]
