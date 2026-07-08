"""信誉系统 — 自动计分 + 等级计算"""

from app.modules.tenant.models import User

# 行为分值
SCORE_MAP = {
    "create_post": 1,
    "post_liked": 1,
    "post_commented": 2,
    "trade_completed": 5,
    "reported_valid": -10,
}


def compute_level(score: int) -> str:
    """根据分值返回等级"""
    if score >= 80: return "diamond"
    if score >= 60: return "platinum"
    if score >= 40: return "gold"
    if score >= 20: return "silver"
    return "bronze"


async def add_reputation(user: User, action: str, db) -> int:
    """给用户加减信誉分，自动更新等级。返回新分数。"""
    delta = SCORE_MAP.get(action, 0)
    if delta == 0:
        return user.reputation_score

    user.reputation_score = max(0, min(100, user.reputation_score + delta))
    user.level = compute_level(user.reputation_score)
    await db.commit()
    return user.reputation_score
