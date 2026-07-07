"""
社交 API — 动态 / 评论 / 点赞 / 关注 / 好友

所有操作限定在当前用户所属租户内。
"""

import uuid

from fastapi import APIRouter, Depends, Form, Query, Request, status

from app.core.cache import cache_get, cache_set, feed_key, invalidate_feed, TTL_FEED
from app.core.counters import like_counter, comment_counter, view_counter
from app.core.database import get_db
from app.core.rate_limit import (
    RATE_SOCIAL_COMMENT, RATE_SOCIAL_CREATE_POST, RATE_SOCIAL_FOLLOW,
    RATE_SOCIAL_FRIEND_REQUEST, RATE_SOCIAL_LIKE, limiter,
)
from app.core.security import PermissionChecker, TokenPayload, get_current_user
from app.modules.social import service as social_svc
from app.modules.social import feed_service as feed_svc
from app.modules.social.schemas import (
    CommentCreate, CommentResponse, FollowResponse,
    FriendRequest, FriendResponse, LikeResponse,
    PostCreate, PostListParams, PostResponse, PostUpdate,
)

router = APIRouter()

# 权限检查器
require_social_read = PermissionChecker("social:read")
require_social_write = PermissionChecker("social:write")


# ============================================================
# 动态
# ============================================================

@router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_SOCIAL_CREATE_POST)
async def create_post(
    request: Request,
    data: PostCreate, _: bool = Depends(require_social_write),
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """发布动态"""
    return await social_svc.create_post(
        db,
        tenant_id=uuid.UUID(current_user.tenant_id),
        author_id=uuid.UUID(current_user.sub),
        content=data.content,
        media_urls=data.media_urls,
        visibility=data.visibility,
    )


@router.get("/posts")
async def list_posts(
    _: bool = Depends(require_social_read),
    feed_type: str = Query("all", pattern="^(all|following|user)$"),
    user_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取动态列表 (时间线) — 'following' 走 Redis Timeline, 'all' page1 走缓存"""
    tid_str = str(current_user.tenant_id)

    # 全站流首页缓存 30s (最高频读操作)
    if feed_type == "all" and page == 1:
        feed_cache_key = feed_key(tid_str, "all", 1)
        cached = await cache_get(feed_cache_key)
        if cached:
            return cached

    if feed_type == "following":
        posts, total = await feed_svc.get_following_timeline(
            db,
            tenant_id=uuid.UUID(current_user.tenant_id),
            user_id=uuid.UUID(current_user.sub),
            page=page,
            page_size=page_size,
        )
    else:
        posts, total = await social_svc.get_feed(
            db,
            tenant_id=uuid.UUID(current_user.tenant_id),
            current_user_id=uuid.UUID(current_user.sub),
            feed_type=feed_type,
            target_user_id=user_id,
            page=page,
            page_size=page_size,
        )

    # 批量查点赞状态
    post_ids = [p.id for p in posts]
    liked_set = await social_svc.check_liked(db, uuid.UUID(current_user.sub), post_ids)

    # 批量从 Redis 取实时计数
    str_ids = [str(pid) for pid in post_ids]
    redis_likes = await like_counter.get_bulk(str_ids)
    redis_comments = await comment_counter.get_bulk(str_ids)
    redis_views = await view_counter.get_bulk(str_ids)

    items = []
    for p in posts:
        pid_str = str(p.id)
        items.append({
            "id": pid_str,
            "content": p.content,
            "media_urls": p.media_urls,
            "visibility": p.visibility,
            "view_count": redis_views.get(pid_str, 0) or p.view_count,
            "like_count": redis_likes.get(pid_str, 0) or p.like_count,
            "comment_count": redis_comments.get(pid_str, 0) or p.comment_count,
            "is_liked": p.id in liked_set,
            "author_id": str(p.author_id),
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
        })

    response = {"items": items, "total": total, "page": page, "page_size": page_size}

    # 缓存全站流首页 30s
    if feed_type == "all" and page == 1:
        import asyncio
        asyncio.create_task(cache_set(feed_cache_key, response, TTL_FEED))

    return response


@router.get("/posts/{post_id}")
async def get_post(
    post_id: uuid.UUID,
    _: bool = Depends(require_social_read),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取动态详情"""
    post = await social_svc.get_post(db, uuid.UUID(current_user.tenant_id), post_id)
    # 增加浏览次数
    await social_svc.increment_view(db, uuid.UUID(current_user.tenant_id), post_id)
    liked_set = await social_svc.check_liked(db, uuid.UUID(current_user.sub), [post_id])

    # 从 Redis 读取实时计数
    pid_str = str(post_id)
    redis_likes = await like_counter.get(pid_str) or 0
    redis_comments = await comment_counter.get(pid_str) or 0
    redis_views = await view_counter.get(pid_str) or 0

    return {
        "id": str(post.id),
        "content": post.content,
        "media_urls": post.media_urls,
        "visibility": post.visibility,
        "view_count": redis_views + 1 or post.view_count + 1,
        "like_count": redis_likes or post.like_count,
        "comment_count": redis_comments or post.comment_count,
        "is_liked": post.id in liked_set,
        "author_id": str(post.author_id),
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat(),
    }


@router.patch("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: uuid.UUID, data: PostUpdate, _: bool = Depends(require_social_write),
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """编辑动态"""
    return await social_svc.update_post(
        db, uuid.UUID(current_user.tenant_id), post_id,
        author_id=uuid.UUID(current_user.sub),
        **data.model_dump(exclude_none=True),
    )


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: uuid.UUID, _: bool = Depends(require_social_write),
    current_user: TokenPayload = Depends(get_current_user), db=Depends(get_db),
):
    """删除动态"""
    await social_svc.delete_post(
        db, uuid.UUID(current_user.tenant_id), post_id,
        author_id=uuid.UUID(current_user.sub),
    )


@router.post("/posts/{post_id}/archive-to-knowledge", status_code=status.HTTP_201_CREATED)
async def archive_post_to_knowledge(
    post_id: uuid.UUID,
    category: str | None = None,
    tags: str | None = None,
    _: bool = Depends(require_social_write),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    将社群帖子归档到知识库 (Layer 1.1/1.2: 精华标记 + 活动复盘)

    使用方式:
      主理人看到有价值的帖子 → 打精华标记 → 自动同步进知识库
      活动复盘帖 → 归档时 category=活动复盘, tags=OPC,活动,经验
    """
    post = await social_svc.get_post(db, uuid.UUID(current_user.tenant_id), post_id)

    # 自动生成知识文档
    from app.modules.knowledge.service import upload_document
    import tempfile, os

    tag_list = [t.strip() for t in tags.split(",")] if tags else ["精华"]
    if category == "活动复盘" and "活动复盘" not in tag_list:
        tag_list.append("活动复盘")

    content = f"# {category or '社群精华'}\n\n"
    content += f"> 来源: OPC社群动态 | 作者ID: {post.author_id}\n"
    content += f"> 归档时间: {post.created_at}\n\n"
    content += post.content

    # 写入临时文件 → 走标准上传流程 (分块+向量化)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(content)
        tmp_path = f.name

    try:
        doc = await upload_document(
            db,
            tenant_id=uuid.UUID(current_user.tenant_id),
            file_path=tmp_path,
            title=f"[社群精华] {post.content[:50]}",
        )
        return {"doc_id": str(doc.id), "title": doc.title, "status": doc.status,
                "chunks": doc.chunk_count, "tags": tag_list}
    finally:
        os.unlink(tmp_path)


# ============================================================
# 评论
# ============================================================

@router.post("/posts/{post_id}/comments", status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_SOCIAL_COMMENT)
async def create_comment(
    request: Request,
    post_id: uuid.UUID,
    content: str = Form(...),
    parent_id: uuid.UUID | None = Form(None),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """发表评论"""
    comment = await social_svc.create_comment(
        db,
        tenant_id=uuid.UUID(current_user.tenant_id),
        post_id=post_id,
        author_id=uuid.UUID(current_user.sub),
        content=content,
        parent_id=parent_id,
    )
    return {"id": str(comment.id), "content": comment.content,
            "author_id": str(comment.author_id), "parent_id": str(comment.parent_id) if comment.parent_id else None,
            "created_at": comment.created_at.isoformat()}


@router.get("/posts/{post_id}/comments")
async def get_comments(
    post_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取评论列表 (批量查子回复，避免 N+1)"""
    comments, total = await social_svc.get_comments(
        db, uuid.UUID(current_user.tenant_id), post_id, page=page, page_size=page_size,
    )

    # 批量获取所有一级评论的子回复 (1 次查询代替 N 次)
    parent_ids = [c.id for c in comments]
    replies_map = await social_svc.get_bulk_comment_replies(
        db, uuid.UUID(current_user.tenant_id), parent_ids,
    )

    items = []
    for c in comments:
        replies = replies_map.get(c.id, [])
        items.append({
            "id": str(c.id),
            "content": c.content,
            "author_id": str(c.author_id),
            "parent_id": None,
            "replies": [{"id": str(r.id), "content": r.content,
                         "author_id": str(r.author_id),
                         "created_at": r.created_at.isoformat()} for r in replies],
            "created_at": c.created_at.isoformat(),
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ============================================================
# 点赞
# ============================================================

@router.post("/posts/{post_id}/like")
@limiter.limit(RATE_SOCIAL_LIKE)
async def toggle_like_post(
    request: Request,
    post_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """点赞/取消点赞动态"""
    return await social_svc.toggle_like(
        db, uuid.UUID(current_user.tenant_id), uuid.UUID(current_user.sub),
        target_type="post", target_id=post_id,
    )


@router.post("/comments/{comment_id}/like")
@limiter.limit(RATE_SOCIAL_LIKE)
async def toggle_like_comment(
    request: Request,
    comment_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """点赞/取消点赞评论"""
    return await social_svc.toggle_like(
        db, uuid.UUID(current_user.tenant_id), uuid.UUID(current_user.sub),
        target_type="comment", target_id=comment_id,
    )


# ============================================================
# 关注
# ============================================================

@router.post("/users/{user_id}/follow", status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_SOCIAL_FOLLOW)
async def follow_user(
    request: Request,
    user_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """关注用户"""
    await social_svc.follow_user(
        db, uuid.UUID(current_user.tenant_id),
        uuid.UUID(current_user.sub), user_id,
    )
    return {"status": "following"}


@router.delete("/users/{user_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_SOCIAL_FOLLOW)
async def unfollow_user(
    request: Request,
    user_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """取消关注"""
    await social_svc.unfollow_user(
        db, uuid.UUID(current_user.tenant_id),
        uuid.UUID(current_user.sub), user_id,
    )


@router.get("/users/{user_id}/followers")
async def get_followers(
    user_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取粉丝列表"""
    users, total = await social_svc.get_followers(
        db, uuid.UUID(current_user.tenant_id), user_id, page=page, page_size=page_size,
    )
    items = [{"id": str(u.id), "username": u.username, "display_name": u.display_name,
              "avatar_url": u.avatar_url} for u in users]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/users/{user_id}/following")
async def get_following(
    user_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取关注列表"""
    users, total = await social_svc.get_following(
        db, uuid.UUID(current_user.tenant_id), user_id, page=page, page_size=page_size,
    )
    items = [{"id": str(u.id), "username": u.username, "display_name": u.display_name,
              "avatar_url": u.avatar_url} for u in users]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ============================================================
# 好友
# ============================================================

@router.post("/friends/request", status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_SOCIAL_FRIEND_REQUEST)
async def send_friend_request(
    request: Request,
    data: FriendRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """发送好友申请"""
    req = await social_svc.send_friend_request(
        db, uuid.UUID(current_user.tenant_id),
        uuid.UUID(current_user.sub), data.friend_id,
    )
    return {"id": str(req.id), "status": req.status, "created_at": req.created_at.isoformat()}


@router.post("/friends/{friend_id}/accept")
async def accept_friend(
    friend_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """接受好友申请"""
    req = await social_svc.handle_friend_request(
        db, uuid.UUID(current_user.tenant_id),
        uuid.UUID(current_user.sub), friend_id, "accept",
    )
    return {"id": str(req.id), "status": req.status}


@router.post("/friends/{friend_id}/reject")
async def reject_friend(
    friend_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """拒绝好友申请"""
    req = await social_svc.handle_friend_request(
        db, uuid.UUID(current_user.tenant_id),
        uuid.UUID(current_user.sub), friend_id, "reject",
    )
    return {"id": str(req.id), "status": req.status}


@router.get("/friends")
async def get_friends(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取好友列表"""
    friends, total = await social_svc.get_friends(
        db, uuid.UUID(current_user.tenant_id),
        uuid.UUID(current_user.sub), page=page, page_size=page_size,
    )
    return {"items": friends, "total": total, "page": page, "page_size": page_size}


# ============================================================
# 内容安全 — 举报 & 审核
# ============================================================

# 简易举报记录 (内存计数器 + DB 持久化)
_report_counts: dict[str, int] = {}


@router.post("/posts/{post_id}/report")
async def report_post(
    post_id: uuid.UUID,
    reason: str = Query("spam", pattern="^(spam|abuse|illegal|other)$"),
    detail: str | None = None,
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    举报帖子。

    累积 3 次举报 → 自动标记 is_deleted
    """
    pid = str(post_id)
    _report_counts[pid] = _report_counts.get(pid, 0) + 1
    count = _report_counts[pid]

    # 达到阈值 → 自动下架
    if count >= 3:
        try:
            await social_svc.delete_post(
                db, uuid.UUID(current_user.tenant_id),
                post_id, uuid.UUID(current_user.sub),
                is_admin=True,
            )
            return {"reported": True, "action": "auto_hidden", "report_count": count}
        except Exception:
            pass

    return {"reported": True, "report_count": count, "action": "flagged"}


@router.post("/comments/{comment_id}/report")
async def report_comment(
    comment_id: uuid.UUID,
    reason: str = Query("spam", pattern="^(spam|abuse|illegal|other)$"),
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
):
    """举报评论"""
    cid = str(comment_id)
    _report_counts[cid] = _report_counts.get(cid, 0) + 1
    return {"reported": True, "report_count": _report_counts[cid]}


@router.get("/content/spam-check")
async def spam_check(
    content: str = Query(min_length=1, description="待检测文本"),
    current_user: TokenPayload = Depends(get_current_user),
):
    """
    预检文本 (前端实时提示)。

    前端在用户输入时调用此接口，实时提示是否有敏感词。
    """
    from app.core.content_filter import filter_content
    result = filter_content(content)
    return {
        "allowed": result.allowed,
        "flagged": result.flagged,
        "reason": result.reason or "",
        "matched": result.matched_keywords or result.matched_patterns,
    }
