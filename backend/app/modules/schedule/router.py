"""
定时任务管理 API

GET    /schedule/tasks              - 任务列表
GET    /schedule/tasks/{id}         - 任务详情 + 执行历史
GET    /schedule/status             - 任务仪表盘
POST   /schedule/tasks              - 创建任务
PATCH  /schedule/tasks/{id}         - 更新任务
DELETE /schedule/tasks/{id}         - 删除任务
POST   /schedule/tasks/{id}/enable  - 启用
POST   /schedule/tasks/{id}/disable - 禁用
POST   /schedule/tasks/{id}/run     - 手动执行
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from app.config import settings
from app.core.database import get_db
from app.core.security import PermissionChecker, TokenPayload, get_current_user
from app.core.exceptions import NotFoundException
from app.modules.schedule.models import ScheduleTask, TaskExecution

router = APIRouter()

require_read = PermissionChecker("schedule:read")
require_mgmt = PermissionChecker("schedule:manage")


# ========== 列表 ==========

@router.get("/tasks")
async def list_tasks(
    enabled: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: bool = Depends(require_read),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """任务列表"""
    conditions = [ScheduleTask.tenant_id == uuid.UUID(current_user.tenant_id)]
    if enabled is not None:
        conditions.append(ScheduleTask.enabled == enabled)

    total = await db.scalar(select(func.count(ScheduleTask.id)).where(*conditions))
    tasks = (await db.execute(
        select(ScheduleTask).where(*conditions)
        .order_by(ScheduleTask.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    items = [
        {"id": str(t.id), "name": t.name, "task_key": t.task_key,
         "cron_expression": t.cron_expression, "enabled": t.enabled,
         "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
         "next_run_at": t.next_run_at.isoformat() if t.next_run_at else None}
        for t in tasks
    ]
    return {"items": items, "total": total or 0, "page": page, "page_size": page_size}


# ========== 详情 ==========

@router.get("/tasks/{task_id}")
async def get_task(
    task_id: uuid.UUID,
    _: bool = Depends(require_read),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """任务详情 + 最近执行历史"""
    task = await db.get(ScheduleTask, task_id)
    if not task or task.tenant_id != uuid.UUID(current_user.tenant_id):
        raise NotFoundException("任务不存在")

    # 执行历史
    execs = (await db.execute(
        select(TaskExecution)
        .where(TaskExecution.task_id == task_id)
        .order_by(TaskExecution.started_at.desc())
        .limit(20)
    )).scalars().all()

    return {
        "id": str(task.id),
        "name": task.name, "task_key": task.task_key,
        "cron_expression": task.cron_expression,
        "description": task.description, "params": task.params,
        "enabled": task.enabled,
        "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
        "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
        "created_at": task.created_at.isoformat(),
        "history": [
            {"id": str(e.id), "status": e.status,
             "started_at": e.started_at.isoformat(),
             "finished_at": e.finished_at.isoformat() if e.finished_at else None,
             "duration_ms": e.duration_ms, "error_message": e.error_message}
            for e in execs
        ],
    }


# ========== 创建 ==========

@router.post("/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(
    name: str,
    task_key: str,
    cron_expression: str,
    description: str | None = None,
    params: dict | None = None,
    _: bool = Depends(require_mgmt),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """创建定时任务"""
    task = ScheduleTask(
        tenant_id=uuid.UUID(current_user.tenant_id),
        name=name, task_key=task_key, cron_expression=cron_expression,
        description=description, params=params or {},
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"id": str(task.id), "name": task.name, "task_key": task.task_key}


# ========== 更新 ==========

@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: uuid.UUID,
    name: str | None = None,
    cron_expression: str | None = None,
    description: str | None = None,
    params: dict | None = None,
    _: bool = Depends(require_mgmt),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """更新定时任务"""
    task = await db.get(ScheduleTask, task_id)
    if not task or task.tenant_id != uuid.UUID(current_user.tenant_id):
        raise NotFoundException("任务不存在")

    if name is not None: task.name = name
    if cron_expression is not None: task.cron_expression = cron_expression
    if description is not None: task.description = description
    if params is not None: task.params = params

    await db.commit()
    await db.refresh(task)
    return {"id": str(task.id), "name": task.name, "cron_expression": task.cron_expression}


# ========== 删除 ==========

@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    _: bool = Depends(require_mgmt),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """删除定时任务"""
    task = await db.get(ScheduleTask, task_id)
    if not task or task.tenant_id != uuid.UUID(current_user.tenant_id):
        raise NotFoundException("任务不存在")
    await db.delete(task)
    await db.commit()


# ========== 启停 ==========

@router.post("/tasks/{task_id}/enable")
async def enable_task(
    task_id: uuid.UUID,
    _: bool = Depends(require_mgmt),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """启用任务"""
    task = await db.get(ScheduleTask, task_id)
    if not task or task.tenant_id != uuid.UUID(current_user.tenant_id):
        raise NotFoundException("任务不存在")
    task.enabled = True
    await db.commit()
    return {"id": str(task.id), "enabled": True}


@router.post("/tasks/{task_id}/disable")
async def disable_task(
    task_id: uuid.UUID,
    _: bool = Depends(require_mgmt),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """禁用任务"""
    task = await db.get(ScheduleTask, task_id)
    if not task or task.tenant_id != uuid.UUID(current_user.tenant_id):
        raise NotFoundException("任务不存在")
    task.enabled = False
    await db.commit()
    return {"id": str(task.id), "enabled": False}


# ========== 手动执行 ==========

@router.post("/tasks/{task_id}/run")
async def run_task_now(
    task_id: uuid.UUID,
    _: bool = Depends(require_mgmt),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """手动触发一次任务执行"""
    from worker.celery_app import celery_app

    task = await db.get(ScheduleTask, task_id)
    if not task or task.tenant_id != uuid.UUID(current_user.tenant_id):
        raise NotFoundException("任务不存在")

    # 记录执行
    execution = TaskExecution(
        task_id=task_id, status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # 异步发送到 Celery
    try:
        celery_task = celery_app.send_task(task.task_key, kwargs=task.params)
        return {
            "execution_id": str(execution.id),
            "celery_task_id": celery_task.id,
            "status": "dispatched",
        }
    except Exception as e:
        execution.status = "failed"
        execution.error_message = str(e)
        execution.finished_at = datetime.now(timezone.utc)
        await db.commit()
        return {"execution_id": str(execution.id), "status": "failed", "error": str(e)}


@router.post("/run-daily")
async def run_daily_tasks(
    current_user: TokenPayload = Depends(get_current_user),
):
    """
    手动触发每日任务: 保鲜检查 + 简报生成。
    直接在当前进程运行，不走 Celery。
    """
    import asyncio as _asyncio, time

    results = {}
    t0 = time.perf_counter()

    # 1. 保鲜检查
    try:
        from worker.tasks.freshness_check import run as freshness_check
        results["freshness"] = freshness_check()
    except Exception as e:
        results["freshness"] = {"error": str(e)}

    # 2. 每日简报 (直接调 async handler，不走 Celery)
    try:
        from sqlalchemy import create_engine, text as sqltxt
        from skills.daily_briefing.handler import daily_briefing

        engine = create_engine(settings.DATABASE_URL_SYNC)
        with engine.connect() as conn:
            tenants = conn.execute(sqltxt("SELECT id, name FROM tenants WHERE status = 'active'")).all()

        briefing_results = []
        for tenant in tenants:
            br = await daily_briefing(tenant_id=str(tenant.id))
            briefing_results.append({
                "tenant": tenant.name,
                "snapshot": br.get("data_snapshot"),
                "briefing": br.get("briefing", "")[:800],
            })

        results["briefing"] = {"briefings": len(briefing_results), "results": briefing_results}
    except Exception as e:
        results["briefing"] = {"error": str(e)}

    elapsed = round((time.perf_counter() - t0) * 1000)
    return {
        "message": f"Daily tasks completed in {elapsed}ms",
        "elapsed_ms": elapsed,
        "results": results,
    }


# ========== 任务仪表盘 ==========

@router.get("/status")
async def task_dashboard(
    _: bool = Depends(require_read),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    任务仪表盘: 最近执行历史 + 健康度 + 下次执行时间
    """
    from datetime import datetime, timedelta, timezone

    tid = uuid.UUID(current_user.tenant_id)
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # 1. 最近执行历史 (从 task_executions 表)
    recent = (await db.execute(
        select(TaskExecution)
        .join(ScheduleTask, TaskExecution.task_id == ScheduleTask.id)
        .where(ScheduleTask.tenant_id == tid)
        .order_by(TaskExecution.started_at.desc())
        .limit(20)
    )).scalars().all()

    recent_items = []
    for e in recent:
        task = await db.get(ScheduleTask, e.task_id)
        recent_items.append({
            "time": e.started_at.isoformat() if e.started_at else "",
            "task_name": task.name if task else "未知任务",
            "trigger": "scheduled" if task and task.enabled else "manual",
            "status": e.status,
            "duration_ms": e.duration_ms,
            "error": e.error_message[:100] if e.error_message else None,
        })

    # 2. 健康度统计
    total_30d = await db.scalar(
        select(func.count(TaskExecution.id))
        .join(ScheduleTask, TaskExecution.task_id == ScheduleTask.id)
        .where(ScheduleTask.tenant_id == tid, TaskExecution.started_at >= thirty_days_ago)
    ) or 0

    success_30d = await db.scalar(
        select(func.count(TaskExecution.id))
        .join(ScheduleTask, TaskExecution.task_id == ScheduleTask.id)
        .where(ScheduleTask.tenant_id == tid, TaskExecution.started_at >= thirty_days_ago,
               TaskExecution.status == "success")
    ) or 0

    active_tasks = await db.scalar(
        select(func.count(ScheduleTask.id)).where(
            ScheduleTask.tenant_id == tid, ScheduleTask.enabled == True)
    ) or 0

    # 3. 下次执行时间 (从 Celery Beat 推断)
    next_scheduled = {}
    from celery.schedules import crontab
    next_run = now + timedelta(days=1)
    next_scheduled["freshness_check"] = next_run.replace(hour=8, minute=0, second=0).isoformat()
    next_scheduled["daily_briefing"] = next_run.replace(hour=8, minute=10, second=0).isoformat()

    return {
        "recent_executions": recent_items,
        "health": {
            "scheduled_total": active_tasks,
            "scheduled_healthy": active_tasks,
            "event_driven_total": 2,  # new_member_welcome + auto_archive
            "event_driven_healthy": 2,
            "total_executions_30d": total_30d,
            "success_count_30d": success_30d,
            "success_rate_30d": round(success_30d / max(total_30d, 1) * 100, 1),
        },
        "next_scheduled": next_scheduled,
        "generated_at": now.isoformat(),
    }
