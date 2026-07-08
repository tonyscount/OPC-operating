"""
Stop Hook 测试 — 中断条件 / 人工审批 / 预算控制
"""

import pytest
from httpx import AsyncClient

from app.modules.agent.stop_hook import (
    StopHook,
    StopHookException,
    StopReason,
    StopSignal,
    stop_hook,
)


@pytest.fixture
async def auth(client: AsyncClient) -> dict:
    import uuid
    resp = await client.post("/api/v1/auth/register", json={
        "tenant_name": "StopHook Test", "tenant_slug": f"stophook-test-{uuid.uuid4().hex[:8]}",
        "username": "sh_user", "password": "pass123456",
    })
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ============================================================
# Stop Hook 核心测试
# ============================================================

def test_stop_hook_initial_state():
    """初始状态正确"""
    hook = StopHook(max_iterations=10, max_tokens=10000)
    assert hook.max_iterations == 10
    assert hook.max_tokens == 10000
    assert hook._iteration_count == 0
    assert hook._abort_flag == False


def test_stop_signal_creation():
    """StopSignal 数据类"""
    signal = StopSignal(
        reason=StopReason.HARD_STOP,
        message="安全违规",
        checkpoint="before_tool_call",
        details={"tool": "execute_sql"},
    )
    assert signal.reason == StopReason.HARD_STOP
    assert signal.can_resume == False
    assert signal.requires_approval == False


@pytest.mark.asyncio
async def test_iteration_limit():
    """迭代次数超限触发 ITERATION_STOP"""
    hook = StopHook(max_iterations=3)
    hook._start_time = 0

    # 正常通过
    await hook.check("start")
    await hook.check("after_iteration", {"iteration": 1})
    await hook.check("after_iteration", {"iteration": 2})

    # 第 3 次应触发
    with pytest.raises(StopHookException) as exc:
        await hook.check("after_iteration", {"iteration": 3})
    assert exc.value.signal.reason == StopReason.ITERATION_STOP


@pytest.mark.asyncio
async def test_budget_stop():
    """Token 预算耗尽触发 BUDGET_STOP"""
    hook = StopHook(max_tokens=5000)
    hook._start_time = 0

    with pytest.raises(StopHookException) as exc:
        await hook.check("after_llm_call", {"tokens_used": 6000})
    assert exc.value.signal.reason == StopReason.BUDGET_STOP


@pytest.mark.asyncio
async def test_user_abort():
    """用户手动取消"""
    hook = StopHook()
    hook._start_time = 0
    hook.abort()

    with pytest.raises(StopHookException) as exc:
        await hook.check("before_llm_call")
    assert exc.value.signal.reason == StopReason.USER_ABORT


@pytest.mark.asyncio
async def test_dangerous_tool_soft_stop():
    """危险工具触发 SOFT_STOP (需审批)"""
    hook = StopHook(enable_dangerous_tool_block=True)
    hook._start_time = 0

    with pytest.raises(StopHookException) as exc:
        await hook.check("before_tool_call", {"tool_name": "delete_user", "tool_args": {"user_id": "123"}})

    signal = exc.value.signal
    assert signal.reason == StopReason.SOFT_STOP
    assert signal.requires_approval == True
    assert signal.can_resume == True
    assert signal.approval_id is not None


@pytest.mark.asyncio
async def test_dangerous_tool_block_disabled():
    """关闭危险工具拦截后不触发 SOFT_STOP"""
    hook = StopHook(enable_dangerous_tool_block=False)
    hook._start_time = 0

    # 不应抛出异常
    await hook.check("before_tool_call", {"tool_name": "delete_user", "tool_args": {}})


@pytest.mark.asyncio
async def test_approve_soft_stop():
    """审批通过 SOFT_STOP 后可以继续"""
    hook = StopHook(enable_dangerous_tool_block=True)
    hook._start_time = 0

    approval_id = None
    try:
        await hook.check("before_tool_call", {"tool_name": "delete_user", "tool_args": {}})
    except StopHookException as e:
        approval_id = e.signal.approval_id

    assert approval_id is not None
    assert len(hook._pending_approvals) == 1

    ok = await hook.approve(approval_id)
    assert ok == True
    assert len(hook._pending_approvals) == 0


@pytest.mark.asyncio
async def test_stop_hook_reset():
    """reset 后状态归零"""
    hook = StopHook(max_iterations=5)
    hook._start_time = 100
    hook._iteration_count = 10
    hook.abort()

    hook.reset()
    assert hook._iteration_count == 0
    assert hook._abort_flag == False
    assert hook._start_time is None


# ============================================================
# API 测试
# ============================================================

@pytest.mark.asyncio
async def test_stop_hook_status_api(client: AsyncClient, auth: dict):
    """GET /agent/stop-hook/status"""
    resp = await client.get("/api/v1/agent/stop-hook/status", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "stats" in data
    assert "dangerous_tools" in data


@pytest.mark.asyncio
async def test_stop_hook_abort_api(client: AsyncClient, auth: dict):
    """POST /agent/stop-hook/abort"""
    resp = await client.post("/api/v1/agent/stop-hook/abort", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "已发送取消信号"
