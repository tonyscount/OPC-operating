#!/bin/bash
BASE="http://127.0.0.1:8000/api/v1"
PASS=0; FAIL=0; SKIP=0

ok() { echo "  ✅ $1"; ((PASS++)); }
bad() { echo "  ❌ $1 (got: $2)"; ((FAIL++)); }
skip() { echo "  ⏭️  $1"; ((SKIP++)); }
hdr() { echo ""; echo "══════════════════════════════════════════"; echo "🔍 $1"; echo "══════════════════════════════════════════"; }

# ═══════════════════════════════════════
hdr "1. AUTH — 注册"
# ═══════════════════════════════════════

R=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"tenant_name":"审计测试","tenant_slug":"audit-test","username":"auditor","password":"Audit123456","display_name":"审计员","email":"audit@test.com"}')
CODE=$(echo "$R" | tail -1)
BODY=$(echo "$R" | head -n -1)
if [ "$CODE" = "201" ]; then
  TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
  REFRESH=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])" 2>/dev/null)
  ok "注册成功 (201)"
else
  bad "注册失败" "$CODE: $(echo $BODY | head -c 100)"
fi

# 重复 slug
R2=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"tenant_name":"重复","tenant_slug":"audit-test","username":"dup","password":"Dup123456"}')
[ "$R2" = "409" ] && ok "重复slug返回409" || bad "重复slug应返回409" "$R2"

# 缺少必填字段
R3=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"tenant_name":"","tenant_slug":"","username":"","password":""}')
[ "$R3" = "422" ] && ok "空字段返回422" || bad "空字段应返回422" "$R3"

# 短密码
R4=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"tenant_name":"T","tenant_slug":"short-pw","username":"u","password":"123"}')
[ "$R4" = "422" ] && ok "短密码返回422" || bad "短密码应返回422" "$R4"

[ -z "$TOKEN" ] && echo "FATAL: 无 token" && exit 1

H="Authorization: Bearer $TOKEN"

# ═══════════════════════════════════════
hdr "2. AUTH — 登录 & Token"
# ═══════════════════════════════════════

L=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"tenant_slug":"audit-test","username":"auditor","password":"Audit123456"}')
LCODE=$(echo "$L" | tail -1)
[ "$LCODE" = "200" ] && ok "登录成功 (200)" || bad "登录失败" "$LCODE"

L2=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"tenant_slug":"audit-test","username":"auditor","password":"wrong"}')
[ "$L2" = "401" ] && ok "错误密码返回401" || bad "错误密码应返回401" "$L2"

M=$(curl -s -w "\n%{http_code}" "$BASE/auth/me" -H "$H")
[ "$(echo "$M" | tail -1)" = "200" ] && ok "/me 正常 (200)" || bad "/me 失败" "$(echo "$M" | tail -1)"

M2=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/auth/me")
[ "$M2" = "401" ] && ok "/me 无token返回401" || bad "/me 无token应返回401" "$M2"

RF=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH\"}")
RFCODE=$(echo "$RF" | tail -1)
if [ "$RFCODE" = "200" ]; then
  NEW_TOKEN=$(echo "$RF" | head -n -1 | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
  [ "$NEW_TOKEN" != "$TOKEN" ] && ok "refresh 返回新token" || bad "refresh 返回相同token" ""
else
  bad "refresh 失败" "$RFCODE"
fi

# ═══════════════════════════════════════
hdr "3. TENANT — 租户/组织/角色"
# ═══════════════════════════════════════

TI=$(curl -s -w "\n%{http_code}" "$BASE/tenant/info" -H "$H")
[ "$(echo "$TI" | tail -1)" = "200" ] && ok "租户信息 (200)" || bad "租户信息" "$(echo "$TI" | tail -1)"

O=$(curl -s -w "\n%{http_code}" -X POST "$BASE/tenant/orgs" -H "$H" -H "Content-Type: application/json" \
  -d '{"name":"技术部","code":"tech"}')
[ "$(echo "$O" | tail -1)" = "200" ] && ok "创建组织 (200)" || bad "创建组织" "$(echo "$O" | tail -1)"
ORG_ID=$(echo "$O" | head -n -1 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)

O2=$(curl -s -w "\n%{http_code}" -X POST "$BASE/tenant/orgs" -H "$H" -H "Content-Type: application/json" \
  -d "{\"name\":\"前端组\",\"code\":\"frontend\",\"parent_id\":\"$ORG_ID\"}")
[ "$(echo "$O2" | tail -1)" = "200" ] && ok "创建子组织 (200)" || bad "创建子组织" "$(echo "$O2" | tail -1)"

OT=$(curl -s -w "\n%{http_code}" "$BASE/tenant/orgs" -H "$H")
[ "$(echo "$OT" | tail -1)" = "200" ] && ok "组织树 (200)" || bad "组织树" "$(echo "$OT" | tail -1)"

RL=$(curl -s -w "\n%{http_code}" "$BASE/tenant/roles" -H "$H")
[ "$(echo "$RL" | tail -1)" = "200" ] && ok "角色列表 (200)" || bad "角色列表" "$(echo "$RL" | tail -1)"

PL=$(curl -s -w "\n%{http_code}" "$BASE/tenant/permissions" -H "$H")
[ "$(echo "$PL" | tail -1)" = "200" ] && ok "权限列表 (200)" || bad "权限列表" "$(echo "$PL" | tail -1)"

# ═══════════════════════════════════════
hdr "4. SOCIAL — 动态/评论/点赞"
# ═══════════════════════════════════════

P=$(curl -s -w "\n%{http_code}" -X POST "$BASE/social/posts" -H "$H" -H "Content-Type: application/json" \
  -d '{"content":"审计测试帖子 🚀","visibility":"public"}')
[ "$(echo "$P" | tail -1)" = "201" ] && ok "发帖 (201)" || bad "发帖" "$(echo "$P" | tail -1)"
POST_ID=$(echo "$P" | head -n -1 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)

PE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/social/posts" -H "$H" -H "Content-Type: application/json" \
  -d '{"content":"","visibility":"public"}')
[ "$PE" = "422" ] && ok "空内容拒绝 (422)" || bad "空内容应拒绝" "$PE"

F=$(curl -s -w "\n%{http_code}" "$BASE/social/posts?feed_type=all" -H "$H")
[ "$(echo "$F" | tail -1)" = "200" ] && ok "Feed (200)" || bad "Feed" "$(echo "$F" | tail -1)"

C=$(curl -s -w "\n%{http_code}" -X POST "$BASE/social/posts/$POST_ID/comments" \
  -H "$H" -d 'content=审计评论')
[ "$(echo "$C" | tail -1)" = "201" ] && ok "评论 (201)" || bad "评论" "$(echo "$C" | tail -1)"

LK=$(curl -s -w "\n%{http_code}" -X POST "$BASE/social/posts/$POST_ID/like" -H "$H" -d '')
[ "$(echo "$LK" | tail -1)" = "200" ] && ok "点赞 (200)" || bad "点赞" "$(echo "$LK" | tail -1)"

NA=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/social/posts")
[ "$NA" = "401" ] && ok "未认证Feed返回401" || bad "未认证Feed应返回401" "$NA"

# ═══════════════════════════════════════
hdr "5. KNOWLEDGE — 知识库"
# ═══════════════════════════════════════

KC=$(curl -s -w "\n%{http_code}" -X POST "$BASE/knowledge/categories" \
  -H "$H" -d 'name=技术文档')
[ "$(echo "$KC" | tail -1)" = "201" ] && ok "创建分类 (201)" || bad "创建分类" "$(echo "$KC" | tail -1)"

KCL=$(curl -s -w "\n%{http_code}" "$BASE/knowledge/categories" -H "$H")
[ "$(echo "$KCL" | tail -1)" = "200" ] && ok "分类列表 (200)" || bad "分类列表" "$(echo "$KCL" | tail -1)"

KT=$(curl -s -w "\n%{http_code}" -X POST "$BASE/knowledge/text" \
  -H "$H" -d 'title=OPC平台介绍&content=OPC是一个集人员社交、管理、运营、交易于一体的综合平台，支持多租户架构。')
KTCODE=$(echo "$KT" | tail -1)
if [ "$KTCODE" = "201" ]; then
  ok "上传文本 (201)"
else
  bad "上传文本" "$KTCODE: $(echo "$KT" | head -n -1 | head -c 200)"
fi

KA=$(curl -s -w "\n%{http_code}" -X POST "$BASE/knowledge/ask" \
  -H "$H" -d 'question=OPC平台是什么&top_k=3')
KACODE=$(echo "$KA" | tail -1)
if [ "$KACODE" = "200" ]; then
  HAS=$(echo "$KA" | head -n -1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if d.get('answer') else 'no')" 2>/dev/null)
  [ "$HAS" = "yes" ] && ok "RAG问答有结果" || bad "RAG问答无结果" ""
else
  bad "RAG问答" "$KACODE"
fi

# ═══════════════════════════════════════
hdr "6. AGENT — 智能体"
# ═══════════════════════════════════════

AL=$(curl -s -w "\n%{http_code}" "$BASE/agent/list" -H "$H")
[ "$(echo "$AL" | tail -1)" = "200" ] && ok "Agent列表 (200)" || bad "Agent列表" "$(echo "$AL" | tail -1)"

AD=$(curl -s -w "\n%{http_code}" "$BASE/agent/audit/dimensions" -H "$H")
[ "$(echo "$AD" | tail -1)" = "200" ] && ok "审计维度 (200)" || bad "审计维度" "$(echo "$AD" | tail -1)"

AA=$(curl -s -w "\n%{http_code}" -X POST "$BASE/agent/audit" \
  -H "$H" -H "Content-Type: application/json" \
  -d '{"output":"已实现登录功能和JWT认证","steps_executed":["创建User模型"],"requirements":["登录功能"],"errors":[]}')
if [ "$(echo "$AA" | tail -1)" = "200" ]; then
  ok "手动审计 (200)"
else
  bad "手动审计" "$(echo "$AA" | tail -1)"
fi

# ═══════════════════════════════════════
hdr "7. SKILL & DISCOVER"
# ═══════════════════════════════════════

SK=$(curl -s -w "\n%{http_code}" "$BASE/skills" -H "$H")
SKCODE=$(echo "$SK" | tail -1)
if [ "$SKCODE" = "200" ]; then
  SKC=$(echo "$SK" | head -n -1 | python3 -c "import sys,json; d=json.load(sys.stdin); s=d.get('skills',d); print(len(s) if isinstance(s,list) else '?')" 2>/dev/null)
  ok "技能列表 (200, ${SKC}个)"
else
  bad "技能列表" "$SKCODE"
fi

SD=$(curl -s -w "\n%{http_code}" "$BASE/skills/discover" -H "$H")
[ "$(echo "$SD" | tail -1)" = "200" ] && ok "技能发现 (200)" || bad "技能发现" "$(echo "$SD" | tail -1)"

DF=$(curl -s -w "\n%{http_code}" "$BASE/discover/feed" -H "$H")
[ "$(echo "$DF" | tail -1)" = "200" ] && ok "发现Feed (200)" || bad "发现Feed" "$(echo "$DF" | tail -1)"

US=$(curl -s -w "\n%{http_code}" "$BASE/users/search?q=auditor" -H "$H")
[ "$(echo "$US" | tail -1)" = "200" ] && ok "用户搜索 (200)" || bad "用户搜索" "$(echo "$US" | tail -1)"

SS=$(curl -s -w "\n%{http_code}" "$BASE/search?q=OPC" -H "$H")
[ "$(echo "$SS" | tail -1)" = "200" ] && ok "全文搜索 (200)" || bad "全文搜索" "$(echo "$SS" | tail -1)"

# ═══════════════════════════════════════
hdr "8. DEVICE & OPS & SETTINGS"
# ═══════════════════════════════════════

DV=$(curl -s -w "\n%{http_code}" "$BASE/devices" -H "$H")
[ "$(echo "$DV" | tail -1)" = "200" ] && ok "设备列表 (200)" || bad "设备列表" "$(echo "$DV" | tail -1)"

OPS=$(curl -s -w "\n%{http_code}" "$BASE/ops/dashboard" -H "$H")
[ "$(echo "$OPS" | tail -1)" = "200" ] && ok "Ops Dashboard (200)" || bad "Ops Dashboard" "$(echo "$OPS" | tail -1)"

ST=$(curl -s -w "\n%{http_code}" "$BASE/settings/llm" -H "$H")
[ "$(echo "$ST" | tail -1)" = "200" ] && ok "LLM设置 (200)" || bad "LLM设置" "$(echo "$ST" | tail -1)"

# ═══════════════════════════════════════
hdr "9. CONVERSATION & NOTIFICATION"
# ═══════════════════════════════════════

CV=$(curl -s -w "\n%{http_code}" "$BASE/conversations" -H "$H")
[ "$(echo "$CV" | tail -1)" = "200" ] && ok "会话列表 (200)" || bad "会话列表" "$(echo "$CV" | tail -1)"

NT=$(curl -s -w "\n%{http_code}" "$BASE/notifications" -H "$H")
[ "$(echo "$NT" | tail -1)" = "200" ] && ok "通知列表 (200)" || bad "通知列表" "$(echo "$NT" | tail -1)"

NUC=$(curl -s -w "\n%{http_code}" "$BASE/notifications/unread-count" -H "$H")
[ "$(echo "$NUC" | tail -1)" = "200" ] && ok "未读计数 (200)" || bad "未读计数" "$(echo "$NUC" | tail -1)"

# ═══════════════════════════════════════
hdr "10. SCHEDULE"
# ═══════════════════════════════════════

SC=$(curl -s -w "\n%{http_code}" "$BASE/schedule/tasks" -H "$H")
[ "$(echo "$SC" | tail -1)" = "200" ] && ok "定时任务列表 (200)" || bad "定时任务列表" "$(echo "$SC" | tail -1)"

# ═══════════════════════════════════════
hdr "11. EDGE CASES"
# ═══════════════════════════════════════

SI=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_slug\":\"audit-test\",\"username\":\"admin' OR 1=1 --\",\"password\":\"x\"}")
[ "$SI" = "401" ] && ok "SQL注入被防护 (401)" || bad "SQL注入" "$SI"

NE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/nonexistent/endpoint")
[ "$NE" = "404" ] && ok "不存在端点返回404" || bad "不存在端点" "$NE"

MN=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE/auth/login")
[ "$MN" = "405" ] && ok "错误方法返回405" || bad "错误方法" "$MN"

# ═══════════════════════════════════════
hdr "12. LOGOUT & 吊销验证"
# ═══════════════════════════════════════

LO=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/logout" -H "$H")
[ "$(echo "$LO" | tail -1)" = "200" ] && ok "登出 (200)" || bad "登出" "$(echo "$LO" | tail -1)"

M3=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/auth/me" -H "$H")
[ "$M3" = "401" ] && ok "登出后token已吊销 (401)" || bad "登出后token应吊销" "$M3"

# ═══════════════════════════════════════
echo ""
echo "══════════════════════════════════════════"
echo "              审计完毕"
echo "══════════════════════════════════════════"
echo "  ✅ 通过: $PASS"
echo "  ❌ 失败: $FAIL"
echo "  ⏭️ 跳过: $SKIP"
echo "══════════════════════════════════════════"
