"""
种子数据脚本 —— 开发/测试环境快速初始化。

用法:
    cd backend
    python -m alembic.seed

或通过 Docker:
    docker compose exec api python -m alembic.seed
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database import async_session_factory
from app.modules.tenant.service import create_tenant


async def seed():
    """创建演示租户和管理员"""
    async with async_session_factory() as db:
        # 检查是否已有数据
        from sqlalchemy import select, func
        from app.modules.tenant.models import Tenant

        count = await db.scalar(select(func.count(Tenant.id)))
        if count > 0:
            print(f"✅ 已有 {count} 个租户，跳过 seed")
            return

        # 创建演示租户
        print("🌱 创建演示租户...")
        tenant = await create_tenant(
            db,
            name="演示企业",
            slug="demo",
            plan="pro",
        )

        # 创建演示管理员
        from app.modules.tenant.service import create_user as create_tenant_user
        from app.modules.tenant.models import Role

        result = await db.execute(select(Role).where(Role.tenant_id == tenant.id, Role.name == "管理员"))
        admin_role = result.scalar_one()

        admin = await create_tenant_user(
            db,
            tenant_id=tenant.id,
            username="admin",
            password="admin123456",
            email="admin@demo.com",
            display_name="管理员",
            role_ids=[admin_role.id],
        )
        print(f"✅ 管理员: admin / admin123456 (tenant=demo)")

        # 创建普通成员
        result = await db.execute(select(Role).where(Role.tenant_id == tenant.id, Role.name == "成员"))
        member_role = result.scalar_one()

        member = await create_tenant_user(
            db,
            tenant_id=tenant.id,
            username="zhangsan",
            password="user123456",
            email="zhangsan@demo.com",
            display_name="张三",
            role_ids=[member_role.id],
        )
        print(f"✅ 成员: zhangsan / user123456 (tenant=demo)")
        print("🌱 Seed 完成！")


if __name__ == "__main__":
    asyncio.run(seed())
