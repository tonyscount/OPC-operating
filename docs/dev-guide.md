# OPC Platform — 开发指南

## 快速启动

### 1. 启动基础设施 (仅 DB + Redis)
```bash
docker compose -f docker-compose.dev.yml up -d
```

### 2. 启动后端
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

访问 http://localhost:8000/api/docs 查看 Swagger。

### 3. 数据库迁移
```bash
cd backend
alembic upgrade head              # 执行迁移
alembic revision --autogenerate -m "描述"  # 生成迁移文件
```

### 4. 启动 Worker
```bash
cd backend
celery -A worker.celery_app worker --loglevel=info
celery -A worker.celery_app beat --loglevel=info  # 另一个终端
```

### 5. 全栈启动
```bash
docker compose up -d
```

## 开发规范

### 新建模块
1. 在 `backend/app/modules/<name>/` 创建目录
2. 创建 `__init__.py`, `models.py`, `router.py`, `schemas.py`, `service.py`
3. 在 `backend/app/modules/__init__.py` 中导入 models
4. 在 `backend/app/main.py` 的 `register_routers()` 中注册路由

### 租户隔离
- 所有业务表必须继承 `TenantBase` (自动带 tenant_id)
- 所有查询必须经过 `get_current_user` 依赖 (自动设置租户上下文)
- 不要绕过中间件直接查询

### API 设计
- URL: `/api/v1/<module>/<resource>`
- 分页: 使用 `PaginationParams` 和 `PaginatedResponse`
- 错误: 抛出 `AppException` 子类，由全局处理器统一格式化
