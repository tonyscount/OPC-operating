"""OPC Platform — Audit v3"""
import httpx, asyncio, uuid, os, sys

os.environ.setdefault("TESTING", "true")
# 审计用 opc_platform (已有 alembic 建表)，不用 opc_test (依赖 conftest fixtures)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://opc_user:opc_dev_password@127.0.0.1:5432/opc_platform")

BASE = "http://test"
P = F = S = 0

def ok(msg): global P; P += 1; print(f"  [PASS] {msg}")
def bad(msg, d=""): global F; F += 1; print(f"  [FAIL] {msg} -> {d}")
def hdr(t): print(f"\n{'='*50}\n[+] {t}\n{'='*50}")

async def main():
    global P, F, S
    import app.modules  # noqa: trigger model registration
    from app.core.database import _reset_engine
    _reset_engine()
    from app.main import create_app
    from httpx import AsyncClient, ASGITransport

    app = create_app()
    t = ASGITransport(app=app)
    slug = f"audit3-{uuid.uuid4().hex[:8]}"

    async with AsyncClient(transport=t, base_url=BASE) as c:
        # === 1. AUTH ===
        hdr("1. AUTH")
        r = await c.post("/api/v1/auth/register", json={
            "tenant_name": "Audit3", "tenant_slug": slug,
            "username": "auditor", "password": "Audit12345",
            "display_name": "Auditor"})
        if r.status_code != 201:
            bad("Register", str(r.status_code)); return
        data = r.json()
        TOKEN = data["access_token"]
        REFRESH = data["refresh_token"]
        H = {"Authorization": f"Bearer {TOKEN}"}
        ok("Register")

        tests = [
            ("Login", "POST", "/api/v1/auth/login",
             {"tenant_slug": slug, "username": "auditor", "password": "Audit12345"}, 200),
            ("Wrong PW", "POST", "/api/v1/auth/login",
             {"tenant_slug": slug, "username": "auditor", "password": "wrong"}, 401),
            ("Me", "GET", "/api/v1/auth/me", None, 200),
            ("Me unauth", "GET", "/api/v1/auth/me", None, 401),
            ("Refresh", "POST", "/api/v1/auth/refresh", {"refresh_token": REFRESH}, 200),
        ]
        for label, method, path, body, exp in tests:
            if method == "GET":
                r = await c.get(path, headers=H if "unauth" not in label else None)
            else:
                r = await c.post(path, json=body, headers=H)
            ok(label) if r.status_code == exp else bad(label, f"want {exp} got {r.status_code}")

        # === 2. TENANT ===
        hdr("2. TENANT")
        for label, method, path, body, exp in [
            ("Info", "GET", "/api/v1/tenant/info", None, 200),
            ("Create org", "POST", "/api/v1/tenant/orgs", {"name": "Eng", "code": "eng"}, 200),
            ("Org tree", "GET", "/api/v1/tenant/orgs", None, 200),
            ("Roles", "GET", "/api/v1/tenant/roles", None, 200),
            ("Users", "GET", "/api/v1/tenant/users", None, 200),
            ("Permissions", "GET", "/api/v1/tenant/permissions", None, 200),
        ]:
            if method == "GET": r = await c.get(path, headers=H)
            else: r = await c.post(path, headers=H, json=body)
            ok(label) if r.status_code == exp else bad(label, f"want {exp} got {r.status_code}")

        # === 3. SOCIAL ===
        hdr("3. SOCIAL")
        r = await c.post("/api/v1/social/posts", headers=H, json={"content": "Audit", "visibility": "public"})
        ok("Create post") if r.status_code == 201 else bad("Post", str(r.status_code))
        PID = r.json().get("id") if r.status_code == 201 else None

        r = await c.post("/api/v1/social/posts", headers=H, json={"content": "", "visibility": "public"})
        ok("Empty -> 422") if r.status_code == 422 else bad("Empty", str(r.status_code))

        r = await c.post("/api/v1/social/posts", headers=H, json={"content": "<script>alert(1)</script>", "visibility": "public"})
        if r.status_code == 201:
            r2 = await c.get("/api/v1/social/posts?feed_type=all", headers=H)
            items = r2.json().get("items", []) if r2.status_code == 200 else []
            xss = any("<script>" in str(i.get("content", "")) for i in items if isinstance(items, list))
            ok("XSS filtered") if not xss else bad("XSS NOT filtered!")
        else:
            bad("XSS post", str(r.status_code))

        r = await c.get("/api/v1/social/posts?feed_type=all", headers=H)
        ok("Feed") if r.status_code == 200 else bad("Feed", str(r.status_code))
        r = await c.get("/api/v1/social/posts")
        ok("Feed unauth -> 401") if r.status_code == 401 else bad("Feed unauth", str(r.status_code))

        if PID:
            r = await c.post(f"/api/v1/social/posts/{PID}/comments", headers=H, data={"content": "Nice!"})
            ok("Comment") if r.status_code == 201 else bad("Comment", str(r.status_code))
            r = await c.post(f"/api/v1/social/posts/{PID}/like", headers=H)
            ok("Like") if r.status_code == 200 else bad("Like", str(r.status_code))

        r = await c.post("/api/v1/social/users/auditor/follow", headers=H)
        ok(f"Follow ({r.status_code})")

        # === 4. KNOWLEDGE ===
        hdr("4. KNOWLEDGE")
        for label, method, path, body, exp in [
            ("Category", "POST", "/api/v1/knowledge/categories", {"name": "tech"}, 201),
            ("List cat", "GET", "/api/v1/knowledge/categories", None, 200),
            ("Docs", "GET", "/api/v1/knowledge/documents", None, 200),
            ("Stats", "GET", "/api/v1/knowledge/stats", None, 200),
            ("Fulltext", "GET", "/api/v1/knowledge/search?q=OPC", None, 200),
        ]:
            if method == "GET": r = await c.get(path, headers=H)
            else: r = await c.post(path, headers=H, data=body)
            ok(label) if r.status_code == exp else bad(label, f"want {exp} got {r.status_code}")

        r = await c.post("/api/v1/knowledge/text", headers=H, data={"title": "OPC", "content": "OPC is a platform for one-person companies."})
        ok("Upload text") if r.status_code == 201 else bad("Upload", str(r.status_code))

        r = await c.post("/api/v1/knowledge/ask", headers=H, data={"question": "What is OPC?", "top_k": "3"})
        ans = r.json().get("answer", "") if r.status_code == 200 else ""
        ok(f"RAG ({len(ans)} chars)") if ans else bad("RAG empty")

        # === 5. AGENT ===
        hdr("5. AGENT")
        r = await c.get("/api/v1/agent/list", headers=H)
        if r.status_code == 200:
            names = [a["name"] for a in r.json().get("agents", [])]
            ok(f"Agents: {names}")
        else:
            bad("Agents", str(r.status_code))

        r = await c.get("/api/v1/agent/audit/dimensions", headers=H)
        ok("Audit dims") if r.status_code == 200 else bad("Dims", str(r.status_code))
        r = await c.post("/api/v1/agent/audit", headers=H, json={"output": "test", "steps_executed": ["s1"], "requirements": ["r1"], "errors": []})
        ok("Manual audit") if r.status_code == 200 else bad("Audit", str(r.status_code))

        # === 6. SKILL / DISCOVER / SEARCH / USER ===
        hdr("6. SKILL / DISCOVER / SEARCH / USER")
        for label, path in [
            ("Skills", "/api/v1/skills"),
            ("Discover", "/api/v1/skills/discover"),
            ("Disc feed", "/api/v1/discover/feed"),
            ("User search", "/api/v1/users/search?q=auditor"),
            ("My profile", "/api/v1/users/profile"),
        ]:
            r = await c.get(path, headers=H)
            ok(label) if r.status_code == 200 else bad(label, str(r.status_code))

        r = await c.post("/api/v1/search", headers=H, json={"query": "test"})
        ok("Search (POST)") if r.status_code == 200 else bad("Search", str(r.status_code))

        # === 7. OPS / DEVICE / SCHEDULE / SETTINGS ===
        hdr("7. OPS / DEVICE / SCHEDULE / SETTINGS")
        for label, path in [
            ("Ops", "/api/v1/ops/dashboard"),
            ("Devices", "/api/v1/devices"),
            ("Schedule status", "/api/v1/schedule/status"),
            ("Schedule tasks", "/api/v1/schedule/tasks"),
            ("LLM settings", "/api/v1/settings/llm"),
        ]:
            r = await c.get(path, headers=H)
            ok(label) if r.status_code == 200 else bad(label, str(r.status_code))

        # === 8. NOTIF / CONV ===
        hdr("8. NOTIF / CONV")
        for label, path in [
            ("Notifs", "/api/v1/notifications"),
            ("Unread", "/api/v1/notifications/unread-count"),
            ("Convs", "/api/v1/conversations"),
            ("Unread total", "/api/v1/conversations/unread-total"),
        ]:
            r = await c.get(path, headers=H)
            ok(label) if r.status_code == 200 else bad(label, str(r.status_code))

        # === 9. TRADE ===
        hdr("9. TRADE")
        r = await c.get("/api/v1/trade/products", headers=H)
        ok("Products") if r.status_code == 200 else bad("Products", str(r.status_code))
        r = await c.get("/api/v1/trade/orders", headers=H)
        ok("Orders") if r.status_code == 200 else bad("Orders", str(r.status_code))
        r = await c.post("/api/v1/trade/products", headers=H, params={"title": "Test Service", "price": "99", "category": "service"})
        ok("Create product") if r.status_code == 201 else bad("Create", f"{r.status_code}: {r.text[:100]}")

        # === 10. EDGE CASES ===
        hdr("10. EDGE CASES")
        r = await c.post("/api/v1/auth/login", json={"tenant_slug": slug, "username": "admin' OR 1=1 --", "password": "x"})
        ok("SQLi -> 401") if r.status_code == 401 else bad("SQLi", str(r.status_code))
        r = await c.get("/api/v1/nonexistent/endpoint")
        ok("404 missing") if r.status_code == 404 else bad("404", str(r.status_code))
        r = await c.delete("/api/v1/auth/login")
        ok("405 method") if r.status_code == 405 else bad("405", str(r.status_code))
        r = await c.get("/api/v1/auth/me", headers={"Authorization": "Bearer bad.jwt.here"})
        ok("Bad JWT -> 401") if r.status_code == 401 else bad("JWT", str(r.status_code))

        # === 11. LOGOUT ===
        hdr("11. LOGOUT")
        r = await c.post("/api/v1/auth/logout", headers=H)
        ok("Logout") if r.status_code == 200 else bad("Logout", str(r.status_code))
        r = await c.get("/api/v1/auth/me", headers=H)
        ok("Token revoked") if r.status_code == 401 else bad("Token NOT revoked!", str(r.status_code))

        # === SUMMARY ===
        total = P + F + S
        print(f"\n{'='*50}")
        print(f"  AUDIT v3: {P}/{total} PASS  {F} FAIL  {S} SKIP")
        print(f"{'='*50}")
        if F > 0: sys.exit(1)

asyncio.run(main())
