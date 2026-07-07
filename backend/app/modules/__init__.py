"""模块自动注册入口"""

# 各模块在此导入以确保 SQLAlchemy 模型被注册到 Base.metadata
# 路由在 main.py 中显式注册 (便于查看和控制)

# Phase 0-8: 全模块注册
from app.modules.tenant import models as tenant_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.social import models as social_models  # noqa: F401
from app.modules.social import oa_models as oa_models  # noqa: F401
from app.modules.social import device_models as device_models  # noqa: F401
from app.modules.schedule import models as schedule_models  # noqa: F401
from app.modules.knowledge import models as knowledge_models  # noqa: F401
from app.modules.agent import models as agent_models  # noqa: F401
from app.modules.skill import models as skill_models  # noqa: F401
from app.modules.trade import models as trade_models  # noqa: F401
