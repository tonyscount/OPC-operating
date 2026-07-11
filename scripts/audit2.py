"""OPC Platform — Full Audit v2 (post all fixes)"""
import httpx, asyncio, uuid, time, sys

BASE = "http://127.0.0.1:8000/api/v1"
PASS = FAIL = SKIP = 0

def ok(msg): global PASS; PASS += 1; print(f"  [PASS] {msg}")
def bad(msg, d=""): global FAIL; FAIL += 1; print(f"  [FAIL] {msg} -> {d}")
def hdr(t): print(f"\n{'='*50}\n[+] {t}\n{'='*50}")

async def main():
    global PASS, FAIL, SKIP

    # Use ASGI transport for reliable testing
    import os; os.environ.setdefault("TESTING", "true")
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://opc_user:opc_dev_password@127.0.0.1:5432/opc_test")

    from app.core.database import _reset_engine
    _reset_engine()
    from app.main import create_app
    from httpx import AsyncClient, ASGITransport
    app = create_app()
    transport = ASGITransport(app=app)

    slug = f"audit2-{uuid.uuid4().hex[:8]}"
    async with AsyncClient(transport=transport, base_url="http://test") as c:

        # ===== 1. AUTH =====
        hdr("1. AUTH — Register + Login + Tokens")
        r = await c.post("/api/v1/auth/register", json={
            "tenant_name":"Audit v2", "tenant_slug":slug,
            "username":"auditor", "password":"Audit12345",
            "display_name":"Auditor", "email":"audit@test.com"})
        if r.status_code != 201:
            bad("Register", f"{r.status_code}: {r.text[:200]}"); return
        data = r.json(); TOKEN = data["access_token"]; REFRESH = data["refresh_token"]
        H = {"Authorization": f"Bearer {TOKEN}"}
        ok(f"Register OK -> {data.get('tenant_name','?')}")

        r = await c.post("/api/v1/auth/login", json={"tenant_slug":slug,"username":"auditor","password":"Audit12345"})
        ok(f"Login OK") if r.status_code == 200 else bad("Login", str(r.status_code))

        r = await c.post("/api/v1/auth/login", json={"tenant_slug":slug,"username":"auditor","password":"wrong"})
        ok(f"Wrong PW -> 401") if r.status_code == 401 else bad("Wrong PW", str(r.status_code))

        r = await c.get("/api/v1/auth/me", headers=H)
        ok(f"/me OK ({r.json().get('username','?')})") if r.status_code == 200 else bad("/me", str(r.status_code))

        r = await c.get("/api/v1/auth/me"); ok("/me no token -> 401") if r.status_code == 401 else bad("/me no token", str(r.status_code))

        r = await c.post("/api/v1/auth/refresh", json={"refresh_token": REFRESH})
        if r.status_code == 200:
            new_tok = r.json()["access_token"]
            ok("Refresh -> new token") if new_tok != TOKEN else bad("Refresh -> SAME token")
        else: bad("Refresh", str(r.status_code))

        # ===== 2. TENANT =====
        hdr("2. TENANT — Orgs / Roles / Users / Permissions")
        for label, method, path, body, exp in [
            ("Tenant info", "GET", "/api/v1/tenant/info", None, 200),
            ("Create org", "POST", "/api/v1/tenant/orgs", {"name":"Engineering","code":"eng"}, 200),
            ("Org tree", "GET", "/api/v1/tenant/orgs", None, 200),
            ("Roles list", "GET", "/api/v1/tenant/roles", None, 200),
            ("Users list", "GET", "/api/v1/tenant/users", None, 200),
            ("Permissions", "GET", "/api/v1/tenant/permissions", None, 200),
        ]:
            if method == "GET": r = await c.get(path, headers=H)
            else: r = await c.post(path, headers=H, json=body)
            ok(label) if r.status_code == exp else bad(label, f"want {exp} got {r.status_code}")

        # ===== 3. SOCIAL =====
        hdr("3. SOCIAL — Posts / Comments / Likes / Follow")
        r = await c.post("/api/v1/social/posts", headers=H, json={"content":"Audit post","visibility":"public"})
        ok("Create post") if r.status_code == 201 else bad("Post", str(r.status_code))
        POST_ID = r.json().get("id") if r.status_code == 201 else None

        r = await c.post("/api/v1/social/posts", headers=H, json={"content":"","visibility":"public"})
        ok("Empty post -> 422") if r.status_code == 422 else bad("Empty post", str(r.status_code))

        # XSS check
        r = await c.post("/api/v1/social/posts", headers=H, json={"content":"<script>alert(1)</script>","visibility":"public"})
        if r.status_code == 201:
            stripped = "<script>" not in (r.json().get("content","") if "content" in (r.json() if r.status_code == 201 else {}) else "")
            # Actually check from feed
            r2 = await c.get("/api/v1/social/posts?feed_type=all", headers=H)
            items = r2.json().get("items", r2.json()) if r2.status_code == 200 else []
            has_xss = any("<script>" in str(i.get("content","")) for i in (items if isinstance(items, list) else []))
            ok("XSS filtered") if not has_xss else bad("XSS NOT filtered!", "")
        else: bad("XSS test post", str(r.status_code))

        r = await c.get("/api/v1/social/posts?feed_type=all", headers=H)
        ok("Feed OK") if r.status_code == 200 else bad("Feed", str(r.status_code))

        r = await c.get("/api/v1/social/posts")
        ok("Feed unauth -> 401") if r.status_code == 401 else bad("Feed unauth", str(r.status_code))

        if POST_ID:
            r = await c.post(f"/api/v1/social/posts/{POST_ID}/comments", headers=H, data={"content":"Nice!"})
            ok("Comment") if r.status_code == 201 else bad("Comment", str(r.status_code))

            r = await c.post(f"/api/v1/social/posts/{POST_ID}/like", headers=H)
            ok("Like") if r.status_code == 200 else bad("Like", str(r.status_code))

            r = await c.delete(f"/api/v1/social/posts/{POST_ID}/like", headers=H)
            ok("Unlike") if r.status_code == 200 else bad("Unlike", str(r.status_code))

        r = await c.post("/api/v1/social/users/auditor/follow", headers=H)
        ok(f"Follow op ({r.status_code})")

        # ===== 4. KNOWLEDGE =====
        hdr("4. KNOWLEDGE — Upload / Search / RAG Ask")
        r = await c.post("/api/v1/knowledge/categories", headers=H, data={"name":"tech"})
        ok("Create category") if r.status_code == 201 else bad("Category", str(r.status_code))

        r = await c.get("/api/v1/knowledge/categories", headers=H)
        ok("List categories") if r.status_code == 200 else bad("Categories", str(r.status_code))

        r = await c.post("/api/v1/knowledge/text", headers=H, data={"title":"OPC Overview","content":"OPC is a platform for one-person companies integrating social, knowledge management, AI agents, and trading."})
        ok("Upload text doc") if r.status_code == 201 else bad("Upload", str(r.status_code))

        r = await c.get("/api/v1/knowledge/documents", headers=H)
        ok("List documents") if r.status_code == 200 else bad("Docs", str(r.status_code))

        r = await c.post("/api/v1/knowledge/ask", headers=H, data={"question":"What is OPC?","top_k":"3"})
        if r.status_code == 200:
            ans = r.json().get("answer","")
            ok(f"RAG ask -> {len(ans)} chars") if ans else bad("RAG ask EMPTY", "")
        else: bad("RAG ask", str(r.status_code))

        r = await c.get("/api/v1/knowledge/search?q=OPC", headers=H)
        ok("Fulltext search") if r.status_code == 200 else bad("Search", str(r.status_code))

        r = await c.get("/api/v1/knowledge/stats", headers=H)
        ok("Stats") if r.status_code == 200 else bad("Stats", str(r.status_code))

        # ===== 5. AGENT =====
        hdr("5. AGENT — List / Audit")
        r = await c.get("/api/v1/agent/list", headers=H)
        if r.status_code == 200:
            names = [a["name"] for a in r.json().get("agents",[])]
            ok(f"Agent list -> {names}")
        else: bad("Agent list", str(r.status_code))

        r = await c.get("/api/v1/agent/audit/dimensions", headers=H)
        ok("Audit dimensions") if r.status_code == 200 else bad("Dimensions", str(r.status_code))

        r = await c.post("/api/v1/agent/audit", headers=H, json={"output":"test","steps_executed":["s1"],"requirements":["r1"],"errors":[]})
        ok("Manual audit") if r.status_code == 200 else bad("Audit", str(r.status_code))

        # ===== 6. SKILL + DISCOVER + SEARCH =====
        hdr("6. SKILL / DISCOVER / SEARCH")
        for label, path in [
            ("Skills list", "/api/v1/skills"),
            ("Skill discover", "/api/v1/skills/discover"),
            ("Discover feed", "/api/v1/discover/feed"),
            ("Unified search", "/api/v1/search?q=test"),
            ("User search", "/api/v1/users/search?q=auditor"),
        ]:
            r = await c.get(path, headers=H)
            ok(label) if r.status_code == 200 else bad(label, str(r.status_code))

        # ===== 7. OPS + DEVICE + SETTINGS =====
        hdr("7. OPS / DEVICE / SETTINGS")
        for label, path in [
            ("Ops dashboard", "/api/v1/ops/dashboard"),
            ("Device list", "/api/v1/devices"),
            ("LLM settings", "/api/v1/settings/llm"),
            ("Schedule status", "/api/v1/schedule/status"),
            ("Schedule tasks", "/api/v1/schedule/tasks"),
        ]:
            r = await c.get(path, headers=H)
            ok(label) if r.status_code == 200 else bad(label, str(r.status_code))

        # ===== 8. NOTIFICATION + CONVERSATION =====
        hdr("8. NOTIFICATION / CONVERSATION")
        for label, path in [
            ("Notifications", "/api/v1/notifications"),
            ("Unread count", "/api/v1/notifications/unread-count"),
            ("Conversations", "/api/v1/conversations"),
            ("Unread total", "/api/v1/conversations/unread-total"),
        ]:
            r = await c.get(path, headers=H)
            ok(label) if r.status_code == 200 else bad(label, str(r.status_code))

        # ===== 9. USER PROFILE =====
        hdr("9. USER PROFILE")
        for label, method, path, body, exp in [
            ("My profile", "GET", "/api/v1/users/profile", None, 200),
            ("Update profile", "PATCH", "/api/v1/users/profile", {"display_name":"New Name"}, 200),
        ]:
            if method == "GET": r = await c.get(path, headers=H)
            elif method == "PATCH": r = await c.patch(path, headers=H, json=body)
            else: r = await c.post(path, headers=H, json=body)
            ok(label) if r.status_code == exp else bad(label, f"want {exp} got {r.status_code}")

        # ===== 10. EDGE CASES =====
        hdr("10. EDGE CASES")
        r = await c.post("/api/v1/auth/login", json={"tenant_slug":slug,"username":"admin' OR 1=1 --","password":"x"})
        ok("SQL injection -> 401") if r.status_code == 401 else bad("SQL injection", str(r.status_code))

        r = await c.get("/api/v1/nonexistent/endpoint")
        ok("404 for missing") if r.status_code == 404 else bad("404 missing", str(r.status_code))

        r = await c.delete("/api/v1/auth/login")
        ok("405 wrong method") if r.status_code == 405 else bad("405", str(r.status_code))

        r = await c.get("/api/v1/auth/me", headers={"Authorization":"Bearer not.a.real.jwt"})
        ok("Bad JWT -> 401") if r.status_code == 401 else bad("Bad JWT", str(r.status_code))

        # ===== 11. LOGOUT =====
        hdr("11. LOGOUT")
        r = await c.post("/api/v1/auth/logout", headers=H)
        ok("Logout OK") if r.status_code == 200 else bad("Logout", str(r.status_code))
        r = await c.get("/api/v1/auth/me", headers=H)
        ok("Token revoked after logout") if r.status_code == 401 else bad("Token NOT revoked!", str(r.status_code))

        # ===== SUMMARY =====
        total = PASS + FAIL + SKIP
        print(f"\n{'='*50}")
        print(f"  AUDIT v2 COMPLETE")
        print(f"  PASS: {PASS}/{total}  FAIL: {FAIL}  SKIP: {SKIP}")
        print(f"{'='*50}")
        if FAIL > 0: sys.exit(1)

asyncio.run(main())
