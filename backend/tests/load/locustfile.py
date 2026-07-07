"""
OPC Platform — 负载测试 (Locust)

模拟真实用户行为:
  - 60% 浏览 Feed + 帖子详情
  - 20% 发帖 + 评论
  - 10% 搜索 + 发现
  -  5% 点赞
  -  5% 注册/登录

用法:
    cd backend/tests/load
    locust -f locustfile.py --host=http://localhost:8000

    # 无 UI 模式 (CI):
    locust -f locustfile.py --host=http://localhost:8000 --headless -u 50 -r 5 -t 60s
"""

import random
import string
import uuid

from locust import HttpUser, between, task

# ═══════════════════════════════════════════════
# 测试数据池 — 避免相同的请求触发缓存
# ═══════════════════════════════════════════════

POST_CONTENTS = [
    "今天OPC平台运行稳定 #运维日报",
    "新上线了PLC监控面板，数据刷新很快",
    "OPC UA协议在工业场景中的应用心得",
    "分享一个远程运维的排错案例",
    "周末给网关做了固件升级，一切正常",
    "传感器数据采集频率优化方案讨论",
    "最近在调研边缘计算方案，有推荐吗",
    "工业互联网平台的技术选型思考",
    "MQTT和OPC UA在数据采集中怎么选",
    "工厂数字化转型的第一步是什么",
]

COMMENT_CONTENTS = [
    "学习了，感谢分享",
    "这个方案不错，我们也试试",
    "有更详细的文档吗",
    "赞同，工业场景确实需要这个",
    "请问是如何解决延迟问题的",
]

SEARCH_QUERIES = [
    "OPC UA",
    "传感器",
    "运维",
    "网关",
    "PLC",
    "边缘计算",
    "数字化转型",
]

# 共享状态: 所有虚拟用户共享已创建的帖子 ID 池
POST_POOL: list[str] = []
CREATED_TENANTS: dict[str, dict] = {}  # slug -> {token, user_id}


class OPCUser(HttpUser):
    """
    OPC 平台虚拟用户。

    每个虚拟用户:
      1. 注册/登录获取 Token
      2. 按权重执行不同操作
      3. 每次请求间隔 1-5 秒 (模拟真实用户)
    """

    wait_time = between(1, 5)
    token: str = ""
    tenant_slug: str = ""
    user_id: str = ""

    def on_start(self):
        """用户启动: 注册新账号"""
        slug = f"load{uuid.uuid4().hex[:8]}"
        self.tenant_slug = slug

        with self.client.post(
            "/api/v1/auth/register",
            json={
                "tenant_name": f"LoadTest{uuid.uuid4().hex[:4]}",
                "tenant_slug": slug,
                "username": f"u{uuid.uuid4().hex[:6]}",
                "password": "LoadTest123",
                "display_name": f"LT{uuid.uuid4().hex[:4]}",
            },
            catch_response=True,
            name="Register",
        ) as r:
            if r.status_code == 201:
                data = r.json()
                self.token = data.get("access_token", "")
                self.user_id = self._extract_user_id(self.token)
                # 共享已创建的租户信息
                CREATED_TENANTS[slug] = {
                    "token": self.token,
                    "user_id": self.user_id,
                }
                r.success()
            else:
                r.failure(f"Register failed: {r.text[:100]}")

    # ═══ 60% 权重: 浏览 ═══

    @task(30)
    def browse_feed(self):
        """浏览全站动态流"""
        if not self.token:
            return
        feed_type = random.choice(["all", "following"])
        with self.client.get(
            f"/api/v1/social/posts?feed_type={feed_type}&page=1&page_size=10",
            headers=self._auth(),
            name="Feed",
        ) as r:
            if r.status_code == 200:
                # 收集帖子 ID 供后续使用
                items = r.json().get("items", [])
                for item in items[:3]:
                    if item["id"] not in POST_POOL:
                        POST_POOL.append(item["id"])

    @task(20)
    def view_post_detail(self):
        """浏览帖子详情"""
        if not self.token:
            return
        pid = self._random_post()
        if not pid:
            return
        with self.client.get(
            f"/api/v1/social/posts/{pid}",
            headers=self._auth(),
            name="Post Detail",
        ) as r:
            pass

    @task(5)
    def view_discover(self):
        """浏览发现页"""
        if not self.token:
            return
        self.client.get(
            "/api/v1/discover/feed?page=1",
            headers=self._auth(),
            name="Discover",
        )

    @task(5)
    def view_notifications(self):
        """查看通知"""
        if not self.token:
            return
        self.client.get(
            "/api/v1/notifications",
            headers=self._auth(),
            name="Notifications",
        )

    # ═══ 20% 权重: 创作 ═══

    @task(10)
    def create_post(self):
        """发帖"""
        if not self.token:
            return
        content = random.choice(POST_CONTENTS)
        with self.client.post(
            "/api/v1/social/posts",
            json={"content": content, "visibility": "public"},
            headers=self._auth(),
            name="Create Post",
        ) as r:
            if r.status_code == 201:
                pid = r.json().get("id", "")
                if pid and len(POST_POOL) < 100:
                    POST_POOL.append(pid)

    @task(10)
    def create_comment(self):
        """评论"""
        if not self.token:
            return
        pid = self._random_post()
        if not pid:
            return
        content = random.choice(COMMENT_CONTENTS)
        self.client.post(
            f"/api/v1/social/posts/{pid}/comments",
            data={"content": content},
            headers=self._auth(),
            name="Create Comment",
        )

    # ═══ 10% 权重: 搜索 ═══

    @task(10)
    def search(self):
        """搜索"""
        if not self.token:
            return
        query = random.choice(SEARCH_QUERIES)
        self.client.post(
            "/api/v1/search",
            json={"query": query, "page": 1},
            headers=self._auth(),
            name="Search",
        )

    # ═══ 5% 权重: 互动 ═══

    @task(5)
    def like_post(self):
        """点赞/取消赞"""
        if not self.token:
            return
        pid = self._random_post()
        if not pid:
            return
        self.client.post(
            f"/api/v1/social/posts/{pid}/like",
            headers=self._auth(),
            name="Like Toggle",
        )

    # ═══ 5% 权重: 其他 ═══

    @task(2)
    def refresh_token(self):
        """刷新 Token (模拟长时间在线)"""
        if not self.token:
            return
        self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "test"},
            headers=self._auth(),
            name="Token Refresh",
        )

    @task(2)
    def view_dashboard(self):
        """运营面板"""
        if not self.token:
            return
        self.client.get(
            "/api/v1/ops/dashboard",
            headers=self._auth(),
            name="Dashboard",
        )

    @task(1)
    def health_check(self):
        """健康检查"""
        self.client.get("/health", name="Health")

    # ═══ 辅助 ═══

    def _auth(self):
        return {"Authorization": f"Bearer {self.token}"}

    def _random_post(self) -> str | None:
        if POST_POOL:
            return random.choice(POST_POOL)
        return None

    @staticmethod
    def _extract_user_id(token: str) -> str:
        """从 JWT 中提取 user_id (不解码, 仅标记)"""
        return token[:20] if token else ""
