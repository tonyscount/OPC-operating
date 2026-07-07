# OPC Platform — 本地开发命令
# 用法: make <target>

.PHONY: help

help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ═══ 后端 ═══

dev: ## 启动开发服务器 (hot reload)
	cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

install: ## 安装所有依赖
	cd backend && pip install -r requirements.txt
	cd web && npm install

migrate: ## 运行数据库迁移
	cd backend && python -m alembic upgrade head

migrate-new: ## 创建新迁移 (make migrate-new msg="描述")
	cd backend && python -m alembic revision --autogenerate -m "$(msg)"

seed: ## 填充测试数据
	cd backend && python -m alembic.seed

# ═══ 测试 ═══

test: ## 运行所有测试
	cd backend && python -m pytest tests/ -v --tb=short

test-cov: ## 测试 + 覆盖率报告
	cd backend && python -m pytest tests/ --cov=app --cov-report=term-missing

test-smoke: ## API 冒烟测试
	cd backend/tests/load && python smoke_test.py 2>/dev/null || python -c "\
	import requests; \
	r = requests.post('http://localhost:8000/api/v1/auth/register', json={ \
		'tenant_name':'SmokeTest','tenant_slug':'smoke-999', \
		'username':'smoke','password':'SmokeTest1','display_name':'ST' \
	}); \
	print('Smoke test: OK' if r.status_code == 201 else f'FAIL: {r.status_code}')"

# ═══ 代码质量 ═══

lint: ## Ruff 代码检查
	cd backend && ruff check app/

format: ## Ruff 代码格式化
	cd backend && ruff format app/

typecheck: ## Mypy 类型检查
	cd backend && mypy app/ --ignore-missing-imports || true

check: lint test ## 提交前完整检查

# ═══ 前端 ═══

web-dev: ## 启动前端开发服务器
	cd web && npm run dev

web-build: ## 构建前端生产包
	cd web && npm run build

# ═══ 负载测试 ═══

load: ## 启动 Locust Web UI
	cd backend/tests/load && locust -f locustfile.py --host=http://localhost:8000

load-headless: ## 无界面负载测试 (60s, 50用户)
	cd backend/tests/load && locust -f locustfile.py --host=http://localhost:8000 --headless -u 50 -r 10 -t 60s

# ═══ 工具 ═══

clean: ## 清理临时文件
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf backend/logs/*.log.* 2>/dev/null || true

psql: ## 连接开发数据库
	docker exec -it opc-postgres psql -U opc_user -d opc_platform 2>/dev/null || \
	psql -U opc_user -h localhost -d opc_platform

redis: ## 连接 Redis
	redis-cli 2>/dev/null || docker exec -it opc-redis redis-cli

backup: ## 手动备份数据库
	scripts\backup.bat 2>/dev/null || bash scripts/backup.sh

restore: ## 恢复数据库 (make restore file=backups/xxx.sql)
	psql -U opc_user -h localhost -d opc_platform < $(file)
