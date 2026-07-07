# OPC Platform — 架构文档

> 最后更新: 2026-06-27

## 概述

OPC Platform 是一个集人员社交、管理、运营、交易于一体的移动端平台。

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 |
| 前端 | Flutter 3.x |
| 数据库 | PostgreSQL 15 + pgvector |
| 缓存 | Redis 7 |
| 任务队列 | Celery + Beat |
| 反向代理 | Nginx |
| 部署 | Docker Compose / 腾讯云 CVM |

## 目录结构

```
OPC-operating/
├── backend/          # Python 后端
│   ├── app/          # 应用代码
│   │   ├── core/     # 核心层 (DB/Security/Middleware)
│   │   ├── modules/  # 业务模块
│   │   └── shared/   # 共享基类
│   ├── worker/       # Celery Worker
│   ├── alembic/      # 数据库迁移
│   ├── skills/       # Skill 实现目录
│   └── tests/        # 测试
├── app/              # Flutter 前端
├── nginx/            # Nginx 配置
└── docs/             # 文档
```

## 六大支柱

1. **多租户数据隔离** — RLS + 中间件 + RBAC
2. **内置知识库 (RAG)** — 文档分块 → 向量化 → pgvector 检索 → LLM 生成
3. **多智能体架构** — LangGraph 编排 + 状态持久化 + 安全围栏
4. **Skill 系统** — 接口定义 → 注册发现 → 执行执行
5. **搜索 API** — 前后端联调规范
6. **定时任务** — Celery Beat + 管理面板

## 相关文档

- [API 规范](./api-spec.yaml)
- [开发指南](./dev-guide.md)
