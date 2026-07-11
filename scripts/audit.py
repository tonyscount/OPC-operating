#!/usr/bin/env python3
"""OPC Platform full-module audit script"""
import httpx, asyncio

BASE = "http://127.0.0.1:8000/api/v1"
PASS = FAIL = SKIP = 0

def ok(msg): global PASS; PASS += 1; print(f"  [PASS] {msg}")
def bad(msg, d=""): global FAIL; FAIL += 1; print(f"  [FAIL] {msg} -> {d}")
def hdr(t): print(f"\n{'='*50}\n[+] {t}\n{'='*50}")

def chk(r, code, label):
    if r.status_code == code: ok(label); return True
    else: bad(label, f"want {code} got {r.status_code}: {r.text[:120]}"); return False

async def main():
    global PASS, FAIL, SKIP
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:

        # ===== 1. AUTH - Register =====
        hdr("1. AUTH - Register")
        r = await c.post("/auth/register", json={
            "tenant_name":"Audit Co","tenant_slug":"audit-full-scan",
            "username":"auditor","password":"Audit123456",
            "display_name":"Auditor","email":"audit@test.com"})
        if r.status_code != 201:
            bad("Register", f"{r.status_code}: {r.text[:200]}"); return
        data = r.json()
        TOKEN, REFRESH = data["access_token"], data["refresh_token"]
        H = {"Authorization": f"Bearer {TOKEN}"}
        ok(f"Register OK (201) -> {data.get('tenant_name','?')}")

        # Dup slug
        r = await c.post("/auth/register", json={
            "tenant_name":"Dup","tenant_slug":"audit-full-scan",
            "username":"dup","password":"Dup123456"})
        chk(r, 409, "Dup slug -> 409")

        # Short pw
        r = await c.post("/auth/register", json={
            "tenant_name":"T","tenant_slug":"short-pw",
            "username":"u","password":"123"})
        chk(r, 422, "Short password -> 422")

        # Bad slug format
        r = await c.post("/auth/register", json={
            "tenant_name":"T","tenant_slug":"BAD SLUG!!!",
            "username":"u","password":"Password123"})
        chk(r, 422, "Bad slug -> 422")

        # ===== 2. AUTH - Login & Token =====
        hdr("2. AUTH - Login & Token")
        r = await c.post("/auth/login", json={
            "tenant_slug":"audit-full-scan","username":"auditor","password":"Audit123456"})
        chk(r, 200, "Login OK")

        r = await c.post("/auth/login", json={
            "tenant_slug":"audit-full-scan","username":"auditor","password":"wrong"})
        chk(r, 401, "Wrong password -> 401")

        r = await c.get("/auth/me", headers=H)
        chk(r, 200, "/me OK")
        if r.status_code == 200:
            u = r.json()
            ok(f"  user={u.get('username')} roles={u.get('roles',[])}")

        r = await c.get("/auth/me")
        chk(r, 401, "/me no token -> 401")

        r = await c.post("/auth/refresh", json={"refresh_token": REFRESH})
        if r.status_code == 200:
            new_tok = r.json()["access_token"]
            ok("Refresh -> new token") if new_tok != TOKEN else bad("Refresh -> SAME token")
        else:
            bad("Refresh failed", str(r.status_code))

        # ===== 3. TENANT =====
        hdr("3. TENANT - org/role/user")
        r = await c.get("/tenant/info", headers=H)
        chk(r, 200, "Tenant info")
        if r.status_code == 200:
            t = r.json()
            ok(f"  name={t.get('name')} plan={t.get('plan')} slug={t.get('slug','?')[:30]}...")

        r = await c.post("/tenant/orgs", headers=H, json={"name":"Tech Dept","code":"tech"})
        chk(r, 200, "Create org")
        ORG_ID = r.json().get("id") if r.status_code == 200 else None

        if ORG_ID:
            r = await c.post("/tenant/orgs", headers=H, json={
                "name":"Frontend Team","code":"frontend","parent_id":ORG_ID})
            chk(r, 200, "Create sub-org")

        r = await c.get("/tenant/orgs", headers=H)
        chk(r, 200, "Org tree")
        if r.status_code == 200:
            ok(f"  org count: {len(r.json())}")

        r = await c.get("/tenant/roles", headers=H)
        chk(r, 200, "Role list")
        if r.status_code == 200:
            roles = r.json()
            sys_roles = [x["name"] for x in roles if x.get("is_system")]
            ok(f"  roles: {len(roles)} system: {sys_roles}")

        r = await c.get("/tenant/users", headers=H)
        chk(r, 200, "User list")

        r = await c.get("/tenant/permissions", headers=H)
        chk(r, 200, "Permission list")
        if r.status_code == 200:
            ok(f"  perms: {len(r.json())}")

        # ===== 4. SOCIAL =====
        hdr("4. SOCIAL - posts/comment/like/follow")
        r = await c.post("/social/posts", headers=H, json={
            "content":"Audit test post","visibility":"public"})
        chk(r, 201, "Create post")
        POST_ID = r.json().get("id") if r.status_code == 201 else None

        r = await c.post("/social/posts", headers=H, json={
            "content":"","visibility":"public"})
        chk(r, 422, "Empty content -> 422")

        r = await c.get("/social/posts?feed_type=all", headers=H)
        chk(r, 200, "Feed")
        if r.status_code == 200:
            items = r.json()
            ok(f"  feed items: {len(items) if isinstance(items,list) else '?'}")

        r = await c.get("/social/posts")
        chk(r, 401, "Unauth feed -> 401")

        if POST_ID:
            r = await c.post(f"/social/posts/{POST_ID}/comments", headers=H,
                             data={"content":"Audit comment"})
            chk(r, 201, "Comment")

            r = await c.post(f"/social/posts/{POST_ID}/like", headers=H)
            chk(r, 200, "Like")

            r = await c.delete(f"/social/posts/{POST_ID}/like", headers=H)
            chk(r, 200, "Unlike")

        r = await c.post("/social/posts", headers=H, json={
            "content":"Private post","visibility":"private"})
        chk(r, 201, "Private post")

        r = await c.post("/social/users/auditor/follow", headers=H)
        ok(f"Follow op ({r.status_code})")

        # ===== 5. KNOWLEDGE =====
        hdr("5. KNOWLEDGE - upload/search/ask")
        r = await c.post("/knowledge/categories", headers=H, data={"name":"tech-docs"})
        chk(r, 201, "Create category")

        r = await c.get("/knowledge/categories", headers=H)
        chk(r, 200, "List categories")

        r = await c.post("/knowledge/text", headers=H, data={
            "title":"OPC Platform Overview",
            "content":"OPC is a comprehensive platform integrating social, management, operations, and trading for personnel, supporting multi-tenant architecture and AI agents."})
        chk(r, 201, "Upload text doc")

        r = await c.get("/knowledge/documents", headers=H)
        chk(r, 200, "List documents")

        r = await c.post("/knowledge/ask", headers=H, data={
            "question":"What is OPC platform?", "top_k":"3"})
        if r.status_code == 200:
            ans = r.json().get("answer","")
            ok(f"RAG ask -> answer ({len(ans)} chars)") if ans else bad("RAG ask -> EMPTY answer")
        else:
            bad("RAG ask", f"{r.status_code}: {r.text[:150]}")

        r = await c.get("/knowledge/search?q=OPC", headers=H)
        chk(r, 200, "Fulltext search")

        r = await c.get("/knowledge/stats", headers=H)
        chk(r, 200, "Knowledge stats")
        if r.status_code == 200:
            ok(f"  stats: {r.json()}")

        # ===== 6. AGENT =====
        hdr("6. AGENT")
        r = await c.get("/agent/list", headers=H)
        chk(r, 200, "Agent list")
        if r.status_code == 200:
            names = [a["name"] for a in r.json().get("agents",[])]
            ok(f"  agents: {names}")

        r = await c.get("/agent/audit/dimensions", headers=H)
        chk(r, 200, "Audit dimensions")
        if r.status_code == 200:
            dims = list(r.json().get("dimensions",{}).keys())
            ok(f"  dims: {dims}")

        r = await c.post("/agent/audit", headers=H, json={
            "output":"Implemented login feature with JWT auth, including User model and login API.",
            "steps_executed":["Create User model","Write login API"],
            "requirements":["Login feature","JWT auth"],"errors":[]})
        chk(r, 200, "Manual audit")
        if r.status_code == 200:
            ad = r.json()
            ok(f"  passed={ad.get('passed')} score={ad.get('score')}")

        # ===== 7. SKILL & DISCOVER =====
        hdr("7. SKILL & DISCOVER")
        r = await c.get("/skills", headers=H)
        chk(r, 200, "Skill list")
        if r.status_code == 200:
            body = r.json()
            skills = body.get("skills", body)
            cnt = len(skills) if isinstance(skills, list) else "?"
            ok(f"  skills: {cnt}")
            if isinstance(skills, list) and skills:
                ok(f"  sample: {[(s.get('name','?'), s.get('display_name','?')) for s in skills[:3]]}")

        r = await c.get("/skills/discover", headers=H)
        chk(r, 200, "Skill discover")

        r = await c.get("/discover/feed", headers=H)
        chk(r, 200, "Discover feed")

        # ===== 8. SEARCH =====
        hdr("8. SEARCH")
        r = await c.get("/search?q=OPC", headers=H)
        chk(r, 200, "Unified search")
        if r.status_code == 200:
            sr = r.json()
            ok(f"  posts={sr.get('posts',{}).get('total',0)} docs={sr.get('documents',{}).get('total',0)}")

        r = await c.get("/users/search?q=auditor", headers=H)
        chk(r, 200, "User search")

        # ===== 9. OPS & DEVICE & SETTINGS =====
        hdr("9. OPS & DEVICE & SETTINGS")
        r = await c.get("/ops/dashboard", headers=H)
        chk(r, 200, "Ops dashboard")

        r = await c.get("/devices", headers=H)
        chk(r, 200, "Device list")

        r = await c.get("/settings/llm", headers=H)
        chk(r, 200, "LLM settings")

        # ===== 10. CONVERSATION & NOTIFICATION =====
        hdr("10. CONVERSATION & NOTIFICATION")
        r = await c.get("/conversations", headers=H)
        chk(r, 200, "Conversations")

        r = await c.get("/notifications", headers=H)
        chk(r, 200, "Notifications")

        r = await c.get("/notifications/unread-count", headers=H)
        chk(r, 200, "Unread count")
        if r.status_code == 200:
            ok(f"  unread: {r.json()}")

        # ===== 11. SCHEDULE =====
        hdr("11. SCHEDULE")
        r = await c.get("/schedule/tasks", headers=H)
        chk(r, 200, "Schedule tasks")

        # ===== 12. EDGE CASES =====
        hdr("12. EDGE CASES")
        r = await c.post("/auth/login", json={
            "tenant_slug":"audit-full-scan","username":"admin' OR 1=1 --","password":"x"})
        chk(r, 401, "SQL injection -> 401")

        r = await c.get("/nonexistent/endpoint")
        chk(r, 404, "404 for missing endpoint")

        r = await c.delete("/auth/login")
        chk(r, 405, "405 for wrong method")

        long_str = "A" * 10000
        r = await c.post("/auth/register", json={
            "tenant_name":long_str,"tenant_slug":"long-test",
            "username":"long","password":"LongTest123"})
        ok(f"Long input -> {r.status_code}")

        r = await c.post("/auth/login", content="")
        ok(f"Empty body -> {r.status_code}")

        # ===== 13. LOGOUT =====
        hdr("13. LOGOUT & revoke")
        r = await c.post("/auth/logout", headers=H)
        chk(r, 200, "Logout OK")

        r = await c.get("/auth/me", headers=H)
        chk(r, 401, "Token revoked after logout")

        # ===== SUMMARY =====
        print(f"\n{'='*50}")
        print(f"  AUDIT COMPLETE")
        print(f"  PASS: {PASS}  FAIL: {FAIL}  SKIP: {SKIP}")
        print(f"{'='*50}")

if __name__ == "__main__":
    asyncio.run(main())
