-- ===================================================
-- OPC Platform — 数据库初始化脚本
-- 在 PostgreSQL 容器首次启动时自动执行
-- ===================================================

-- 1. 启用扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID 生成
CREATE EXTENSION IF NOT EXISTS "pgcrypto";        -- 加密函数
CREATE EXTENSION IF NOT EXISTS "vector";          -- pgvector 向量存储 (Phase 3 用)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";         -- 三元组模糊搜索

-- 2. 创建 RLS 用函数
CREATE OR REPLACE FUNCTION set_app_tenant(tid TEXT) RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', tid, false);
END;
$$ LANGUAGE plpgsql;

-- 3. 该函数用作 RLS Policy 的 USING 条件
CREATE OR REPLACE FUNCTION tenant_filter(table_tenant_id UUID) RETURNS BOOLEAN AS $$
DECLARE
    current_tid TEXT;
BEGIN
    current_tid := NULLIF(current_setting('app.current_tenant_id', true), '');
    IF current_tid IS NULL THEN
        RETURN false;  -- 未设置租户上下文 → 拒绝访问
    END IF;
    RETURN table_tenant_id = current_tid::UUID;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- ===================================================
-- 注意: 具体表的 DDL 由 Alembic 迁移管理
-- 此文件仅做扩展和基础函数初始化
-- RLS Policy 在 Alembic 迁移中按表逐个创建
-- ===================================================
