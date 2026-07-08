import { useState, useEffect } from 'react'
import { api } from '../api/client'
import UserPage from './UserPage'

function parseContent(text) {
  if (!text) return ''
  // Parse #tags → styled spans
  let parsed = text.replace(/#(\S+)/g, '<span style="color:var(--accent);font-weight:600;">#$1</span>')
  // Parse @mentions → styled spans
  parsed = parsed.replace(/@(\S+)/g, '<span style="color:#3B82F6;font-weight:600;">@$1</span>')
  return parsed
}

function StatusBubble({ emoji, text, editable, onEdit }) {
  if (!text && !editable) return null
  return (
    <span onClick={editable ? onEdit : undefined} style={{
      display: 'inline-flex', alignItems: 'center', gap: 2, padding: '2px 8px', background: 'var(--accent-subtle)', borderRadius: 10, fontSize: 11, marginLeft: 8,
      cursor: editable ? 'pointer' : 'default',
    }}>
      {emoji || '💬'} {text || '+ 状态'}
    </span>
  )
}

function CommentSection({ postId, expanded }) {
  const [comments, setComments] = useState([]); const [text, setText] = useState('')
  const [replyTo, setReplyTo] = useState(null); const [loading, setLoading] = useState(false)
  const [liked, setLiked] = useState({})

  const loadComments = async () => {
    try {
      const d = await api.getComments(postId)
      setComments(d.items || [])
    } catch (e) {}
  }
  useEffect(() => { if (expanded) loadComments() }, [expanded])

  const addComment = async (parentId = null) => {
    if (!text.trim()) return; setLoading(true)
    try {
      await api.createComment(postId, text.trim())
      setText(''); setReplyTo(null); loadComments()
    } catch (e) {}
    setLoading(false)
  }

  const likeComment = async (commentId) => {
    setLiked(prev => ({ ...prev, [commentId]: !prev[commentId] }))
    try { await api.likeComment(commentId) } catch (e) {}
  }

  if (!expanded) return null

  const CommentItem = ({ c, isReply = false }) => (
    <div style={{ marginBottom: isReply ? 4 : 8, marginLeft: isReply ? 20 : 0 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
        <span style={{ fontWeight: 700, color: 'var(--accent)', fontSize: 11, flexShrink: 0, width: 20, textAlign: 'center', paddingTop: 2 }}>OP</span>
        <div style={{ flex: 1 }}>
          <div style={{ lineHeight: 1.6, fontSize: 13, color: 'var(--text)' }}>{c.content}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
            <span className="caption">{new Date(c.created_at).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
            <button onClick={() => likeComment(c.id)} style={{ ...actBtn, color: liked[c.id] ? '#DC2626' : 'var(--text-3)' }}>
              {liked[c.id] ? '❤️' : '🤍'}
            </button>
            <button onClick={() => { setReplyTo(c.id); setText(''); setText('') }} style={actBtn}>↩ 回复</button>
          </div>
          {c.replies && c.replies.map(r => <CommentItem key={r.id} c={r} isReply />)}
        </div>
      </div>
    </div>
  )

  return (
    <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 10, marginTop: 10 }}>
      {comments.length === 0 && !loading && <div className="caption" style={{ padding: '8px 0', textAlign: 'center' }}>暂无评论</div>}
      {comments.map(c => <CommentItem key={c.id} c={c} />)}
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <input placeholder={replyTo ? `回复评论...` : '写评论...（Enter 发送）'} value={text} onChange={e => setText(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); addComment(replyTo) } }}
          className="input" style={{ flex: 1, fontSize: 12, padding: '6px 10px' }} />
        {replyTo && <button onClick={() => setReplyTo(null)} className="btn-secondary" style={{ height: 34, fontSize: 11 }}>取消</button>}
        <button onClick={() => addComment(replyTo)} disabled={loading || !text.trim()} className="btn" style={{ height: 34, fontSize: 12, padding: '0 14px' }}>{loading ? '...' : '发送'}</button>
      </div>
    </div>
  )
}

const actBtn = { background: 'none', border: 'none', cursor: 'pointer', fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font)', padding: '2px 4px', borderRadius: 4 }

function FriendPanel() {
  const [friends, setFriends] = useState([]); const [requests, setRequests] = useState([]); const [show, setShow] = useState(false)

  const loadFriends = async () => {
    try {
      const d = await api.getFriends()
      setFriends(d.items || [])
    } catch (e) {}
  }
  const addFriend = async (userId) => {
    await api.sendFriendRequest(userId)
    alert('好友申请已发送')
  }
  const acceptFriend = async (id) => { await api.acceptFriend(id); loadFriends() }

  useEffect(() => { if (show) loadFriends() }, [show])

  if (!show) return <button onClick={() => setShow(true)} className="btn-secondary" style={{ fontSize: 12 }}>👥 好友</button>

  return (
    <div className="card" style={{ padding: 14, marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <span className="h2">好友 · {friends.length}</span>
        <button onClick={() => setShow(false)} className="btn-secondary" style={{ fontSize: 11 }}>收起</button>
      </div>
      {friends.length === 0 && <div className="caption" style={{ padding: 12, textAlign: 'center' }}>暂无好友</div>}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {friends.map(f => (
          <span key={f.id} className="tag tag-accent" style={{ fontSize: 12 }}>{f.friend?.display_name || f.friend?.username || 'OP'}</span>
        ))}
      </div>
    </div>
  )
}

export default function SocialPage({ isMobile }) {
  const [posts, setPosts] = useState([]); const [content, setContent] = useState(''); const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState({}); const [feed, setFeed] = useState('all')
  const [profileUserId, setProfileUserId] = useState(null); const [myId, setMyId] = useState(null)
  const [myStatus, setMyStatus] = useState({ emoji: '', text: '' }); const [editingStatus, setEditingStatus] = useState(false)
  const [onlineCount, setOnlineCount] = useState(0)
  const load = (type = 'all') => api.getPosts({ page_size: 50, feed_type: type }).then(d => setPosts(d.items || []))
  useEffect(() => {
    load()
    api.me().then(u => setMyId(u.user_id)).catch(() => {})
    api.getMyStatus().then(d => setMyStatus(d)).catch(() => {})
    fetch('/api/v1/users/online', { headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` } })
      .then(r => r.json()).then(d => setOnlineCount(d.online_count || 0)).catch(() => {})
  }, [])

  const saveStatus = async () => {
    await api.updateMyStatus({ status_text: myStatus.text, mood: myStatus.emoji })
    setEditingStatus(false)
  }

  const createPost = async () => { if (!content.trim()) return; setLoading(true); try { await api.createPost(content); setContent(''); load(feed) } catch (e) { alert(e.message) } setLoading(false) }
  const archivePost = async (id) => { const cat = prompt('归档分类:', '精华') || '精华'; try { await api.archivePost(id, cat, '社群,精华'); alert('已归档'); load(feed) } catch (e) { alert(e.message) } }
  const switchFeed = (type) => { setFeed(type); load(type) }
  const [followingSet, setFollowingSet] = useState(new Set())
  const addFriend = async (userId) => {
    await api.sendFriendRequest(userId)
    alert('好友申请已发送')
  }
  const followUser = async (userId) => {
    setFollowingSet(prev => new Set([...prev, userId]))
    try { await api.followUser(userId) } catch (e) {
      setFollowingSet(prev => { const n = new Set(prev); n.delete(userId); return n })
    }
  }
  const likePost = async (id) => {
    // 乐观更新：先改 UI，再调 API
    setPosts(prev => prev.map(p => {
      if (p.id !== id) return p
      const wasLiked = p.is_liked
      return { ...p, is_liked: !wasLiked, like_count: (p.like_count || 0) + (wasLiked ? -1 : 1) }
    }))
    try { await api.likePost(id) } catch (e) { load() }
  }
  const deletePost = async (id) => { setPosts(prev => prev.filter(p => p.id !== id)); try { await api.deletePost(id) } catch (e) { load() } }
  const toggleExpand = (id) => { setExpanded(prev => { const n = {...prev}; n[id] = !prev[id]; return n }) }

  if (isMobile) return <MobileSocialView {...{ posts, content, setContent, loading, createPost, archivePost, likePost, deletePost, expanded, toggleExpand, feed, switchFeed, followingSet, followUser, myId, profileUserId, setProfileUserId, myStatus, editingStatus, setEditingStatus, saveStatus }} />

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
        <span className="h1" style={{ marginBottom: 0 }}>社群动态</span>
        {onlineCount > 0 && <span style={{ fontSize: 12, color: '#22C55E', marginLeft: 8, fontWeight: 500 }}>🟢 {onlineCount} 在线</span>}
        <div style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
          {['all', 'following'].map(t => (
            <button key={t} onClick={() => switchFeed(t)} className="btn-chip" style={feed === t ? { background: 'var(--accent-subtle)', color: 'var(--accent)', borderColor: 'var(--accent)' } : {}}>
              {t === 'all' ? '全部' : '关注'}
            </button>
          ))}
        </div>
      </div>
      <p style={{ color: 'var(--text-2)', fontSize: 14, marginBottom: 14 }}>分享运维经验，精华内容自动归档知识库。</p>

      {/* Search + Status */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 14, alignItems: 'center' }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <input placeholder="🔍 搜索帖子、文档、用户..." className="input" style={{ paddingLeft: 32 }}
            onKeyDown={async (e) => {
              if (e.key === 'Enter') { try { const d = await api.search(e.target.value); alert(`找到 ${d.total} 条结果`) } catch (err) { alert('搜索失败') } }
            }} />
        </div>
        <button onClick={() => setEditingStatus(true)} className="btn-secondary" style={{ fontSize: 12 }}>
          {myStatus.text || '设置状态'}
        </button>
      </div>

      {editingStatus && (
        <div className="card" style={{ padding: 14, marginBottom: 14, display: 'flex', gap: 8, alignItems: 'center' }}>
          <input placeholder="🟢" value={myStatus.emoji} onChange={e => setMyStatus({ ...myStatus, emoji: e.target.value })} style={{ width: 40, textAlign: 'center' }} className="input" />
          <input placeholder="状态文字，如：运维中" value={myStatus.text} onChange={e => setMyStatus({ ...myStatus, text: e.target.value })} className="input" style={{ flex: 1 }} />
          <button onClick={saveStatus} className="btn" style={{ height: 34, fontSize: 12 }}>保存</button>
          <button onClick={() => setEditingStatus(false)} className="btn-secondary" style={{ height: 34, fontSize: 12 }}>取消</button>
        </div>
      )}

      <FriendPanel />

      <div className="card" style={{ padding: 18, marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ width: 40, height: 40, borderRadius: 8, background: 'var(--accent-subtle)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0, fontWeight: 600 }}>OP</div>
          <textarea placeholder="分享经验..."
            value={content} onChange={e => setContent(e.target.value)}
            className="input" style={{ flex: 1, height: 64, resize: 'none', lineHeight: 1.6 }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12, gap: 8, alignItems: 'center' }}>
          <label style={{ cursor: 'pointer', fontSize: 12, color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 4 }}>
            📷 图片
            <input type="file" accept="image/*" style={{ display: 'none' }}
              onChange={async (e) => {
                const f = e.target.files?.[0]; if (!f) return
                const fd = new FormData(); fd.append('file', f)
                try {
                  const r = await fetch('/api/v1/upload', { method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` }, body: fd })
                  const d = await r.json()
                  if (d.url) setContent(prev => prev + `\n![图片](${d.url})`)
                } catch (err) { alert('上传失败') }
              }} />
          </label>
          <button onClick={createPost} disabled={loading || !content.trim()} className="btn" style={{ opacity: loading || !content.trim() ? .5 : 1 }}>{loading ? '发布中...' : '发布动态'}</button>
        </div>
      </div>

      {posts.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: 48, color: 'var(--text-3)', fontSize: 14 }}>
          {feed === 'following' ? '还没有关注任何人，去"全部"发现更多' : '还没有动态'}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: `repeat(auto-fill, minmax(${isMobile ? '100%' : '360px'}, 1fr))`, gap: 14 }}>
        {posts.map(p => (
          <div key={p.id} className="card enter" style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <button onClick={() => setProfileUserId(p.author_id)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                <div style={{ width: 36, height: 36, borderRadius: 8, background: 'var(--accent-subtle)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, fontWeight: 600 }}>OP</div>
              </button>
              <div style={{ flex: 1 }}>
                <button onClick={() => setProfileUserId(p.author_id)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font)', padding: 0, fontWeight: 600, fontSize: 13, color: 'var(--text)' }}>Engineer_OPC</button>
                <StatusBubble emoji="🟢" text="在线" />
                <div className="caption">{new Date(p.created_at).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</div>
              </div>
              {myId && p.author_id && String(p.author_id) !== String(myId) ? (
                <div style={{ display: 'flex', gap: 4 }}>
                  <button onClick={() => followUser(p.author_id)}
                    className={followingSet.has(p.author_id) ? 'btn-chip active' : 'btn-chip'}
                    style={{ fontSize: 11, padding: '3px 12px' }}>
                    {followingSet.has(p.author_id) ? '已关注' : '+ 关注'}
                  </button>
                  <button onClick={() => addFriend(p.author_id)} className="btn-secondary" style={{ fontSize: 10, padding: '2px 10px' }}>+好友</button>
                </div>
              ) : null}
            </div>
            <p style={{ fontSize: 14, lineHeight: 1.8, color: 'var(--text)', marginBottom: 14 }} dangerouslySetInnerHTML={{ __html: parseContent(p.content) }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, borderTop: '1px solid var(--border-subtle)', paddingTop: 12 }}>
              <button onClick={() => likePost(p.id)} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: p.is_liked ? '#DC2626' : 'var(--text-3)', fontWeight: 500, fontFamily: 'var(--font)', padding: '4px 8px', borderRadius: 6 }}>
                {p.is_liked ? '❤️' : '🤍'} {p.like_count || 0}
              </button>
              <button onClick={() => toggleExpand(p.id)} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: expanded[p.id] ? 'var(--accent)' : 'var(--text-3)', fontWeight: expanded[p.id] ? 600 : 400, fontFamily: 'var(--font)', padding: '4px 8px', borderRadius: 6 }}>
                💬 {p.comment_count || 0}
              </button>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--text-3)', padding: '4px 8px' }}>👁 {p.view_count || 0}</span>
              <div style={{ flex: 1 }} />
              <button onClick={() => archivePost(p.id)} className="btn-secondary" style={{ fontSize: 11, padding: '4px 12px' }}>归档</button>
              <button onClick={() => deletePost(p.id)} style={{ background: 'none', color: 'var(--text-3)', border: 'none', cursor: 'pointer', fontSize: 13, padding: '4px 6px' }}>🗑</button>
            </div>
            <CommentSection postId={p.id} expanded={expanded[p.id]} onToggle={() => toggleExpand(p.id)} />
          </div>
        ))}
      </div>

      {profileUserId && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1000, display: 'flex', justifyContent: 'center', alignItems: 'center', background: 'rgba(15,23,42,.4)' }} onClick={() => setProfileUserId(null)}>
          <div onClick={e => e.stopPropagation()}>
            <UserPage userId={profileUserId} onClose={() => setProfileUserId(null)} />
          </div>
        </div>
      )}
    </div>
  )
}

/* ====== Mobile Social View ====== */
function MobileSocialView({ posts, content, setContent, loading, createPost, likePost, deletePost, expanded, toggleExpand, feed, switchFeed, followingSet, followUser, myId, profileUserId, setProfileUserId, myStatus, setEditingStatus, saveStatus, editingStatus }) {
  const [showCompose, setShowCompose] = useState(false)
  return (
    <div style={{ paddingBottom: 80 }}>
      {/* Feed tabs */}
      <div style={{ display: 'flex', gap: 8, padding: '12px 16px 8px' }}>
        {['all', 'following'].map(t => (
          <button key={t} onClick={() => switchFeed(t)} style={{
            padding: '6px 16px', borderRadius: 20, border: feed === t ? '2px solid var(--accent)' : '1px solid var(--border)',
            background: feed === t ? 'var(--accent-subtle)' : '#fff', color: feed === t ? 'var(--accent)' : 'var(--text-2)',
            fontFamily: 'var(--font)', fontSize: 14, fontWeight: 600, cursor: 'pointer',
          }}>{t === 'all' ? '全部' : '关注'}</button>
        ))}
        <button onClick={() => setEditingStatus(true)} style={{ marginLeft: 'auto', padding: '6px 14px', borderRadius: 20, border: '1px solid var(--border)', background: '#fff', color: 'var(--text-2)', fontFamily: 'var(--font)', fontSize: 13 }}>
          {myStatus.text || '+ 状态'}
        </button>
      </div>

      {editingStatus && (
        <div className="card" style={{ margin: '0 16px 10px', padding: 12, display: 'flex', gap: 6 }}>
          <input placeholder="🟢" value={myStatus.emoji} onChange={e => setMyStatus({ ...myStatus, emoji: e.target.value })} className="input" style={{ width: 48, textAlign: 'center' }} />
          <input placeholder="状态文字" value={myStatus.text} onChange={e => setMyStatus({ ...myStatus, text: e.target.value })} className="input" style={{ flex: 1 }} />
          <button onClick={saveStatus} className="btn" style={{ height: 40 }}>保存</button>
          <button onClick={() => setEditingStatus(false)} className="btn-secondary" style={{ height: 40 }}>取消</button>
        </div>
      )}

      {/* Posts */}
      <div style={{ padding: '0 16px' }}>
        {posts.length === 0 && <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-3)' }}>{feed === 'following' ? '还没有关注任何人' : '暂无动态'}</div>}
        {posts.map(p => (
          <div key={p.id} className="card" style={{ padding: 16, marginBottom: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <button onClick={() => setProfileUserId(p.author_id)} style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}>
                <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--accent-subtle)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, fontWeight: 700 }}>OP</div>
              </button>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 15 }}>Engineer_OPC</div>
                <div className="caption">{new Date(p.created_at).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</div>
              </div>
              {myId && String(p.author_id) !== String(myId) && (
                <button onClick={() => followUser(p.author_id)} className="btn-chip" style={followingSet.has(p.author_id) ? { background: 'var(--accent-subtle)', color: 'var(--accent)' } : {}}>
                  {followingSet.has(p.author_id) ? '已关注' : '+关注'}
                </button>
              )}
            </div>
            <p style={{ fontSize: 15, lineHeight: 1.7, marginBottom: 12 }} dangerouslySetInnerHTML={{ __html: parseContent(p.content) }} />
            <div style={{ display: 'flex', gap: 20, borderTop: '1px solid var(--border-subtle)', paddingTop: 10 }}>
              <button onClick={() => likePost(p.id)} style={{ ...mobBtn, color: p.is_liked ? '#DC2626' : 'var(--text-3)' }}>{p.is_liked ? '❤️' : '🤍'} {p.like_count || 0}</button>
              <button onClick={() => toggleExpand(p.id)} style={{ ...mobBtn, color: expanded[p.id] ? 'var(--accent)' : 'var(--text-3)' }}>💬 {p.comment_count || 0}</button>
              <span style={mobBtn}>👁 {p.view_count || 0}</span>
              <div style={{ flex: 1 }} />
              <button onClick={() => deletePost(p.id)} style={mobBtn}>🗑</button>
            </div>
            {expanded[p.id] && <CommentSection postId={p.id} expanded={true} />}
          </div>
        ))}
      </div>

      {/* Floating compose button */}
      <button onClick={() => setShowCompose(true)} style={{
        position: 'fixed', bottom: 100, right: 20, width: 56, height: 56, borderRadius: 28,
        background: 'var(--accent)', color: '#fff', border: 'none', fontSize: 24,
        boxShadow: '0 4px 20px rgba(15,118,110,.4)', cursor: 'pointer', zIndex: 300,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>✏️</button>

      {showCompose && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 500, background: 'rgba(0,0,0,.5)', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }} onClick={() => setShowCompose(false)}>
          <div onClick={e => e.stopPropagation()} style={{ background: '#fff', borderRadius: '16px 16px 0 0', padding: 16, maxHeight: '60vh' }}>
            <div className="h2" style={{ marginBottom: 10 }}>发布动态</div>
            <textarea placeholder="分享经验..." value={content} onChange={e => setContent(e.target.value)} className="input" style={{ height: 100, resize: 'none', fontSize: 15 }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
              <button onClick={() => setShowCompose(false)} className="btn-secondary" style={{ marginRight: 8 }}>取消</button>
              <button onClick={() => { createPost(); setShowCompose(false) }} disabled={loading || !content.trim()} className="btn">{loading ? '发布中...' : '发布'}</button>
            </div>
          </div>
        </div>
      )}

      {profileUserId && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(15,23,42,.4)' }} onClick={() => setProfileUserId(null)}>
          <div onClick={e => e.stopPropagation()} style={{ maxWidth: '90vw', margin: '60px auto 0' }}>
            <UserPage userId={profileUserId} onClose={() => setProfileUserId(null)} />
          </div>
        </div>
      )}
    </div>
  )
}

const mobBtn = { background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, fontFamily: 'var(--font)', padding: '6px 8px', borderRadius: 6, display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--text-3)' }
