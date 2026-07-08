import { useState, useEffect } from 'react'
import { api } from '../api/client'

const CATEGORIES = [
  { key: 'ops', label: '运维', icon: '🖥' },
  { key: 'hardware', label: '硬件', icon: '🔧' },
  { key: 'automation', label: '自动化', icon: '⚡' },
  { key: 'business', label: '一人公司', icon: '💼' },
  { key: 'general', label: '综合', icon: '💬' },
]

export default function CirclePage({ isMobile }) {
  const [circles, setCircles] = useState([])
  const [category, setCategory] = useState('')
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', slug: '', category: 'general', description: '' })

  const load = async () => {
    setLoading(true)
    try {
      // Use direct fetch until client.js has circle methods
      const params = category ? `?category=${category}` : ''
      const r = await fetch(`/api/v1/social/circles${params}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` }
      })
      const d = await r.json()
      setCircles(d.items || [])
    } catch (e) { /* */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [category])

  const createCircle = async () => {
    if (!form.name.trim() || !form.slug.trim()) return
    const params = new URLSearchParams(form)
    await fetch(`/api/v1/social/circles?${params}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` }
    })
    setShowCreate(false)
    setForm({ name: '', slug: '', category: 'general', description: '' })
    load()
  }

  const joinCircle = async (id) => {
    await fetch(`/api/v1/social/circles/${id}/join`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` }
    })
    load()
  }

  const catLabel = (c) => {
    const found = CATEGORIES.find(x => x.key === c)
    return found ? `${found.icon} ${found.label}` : c
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        <h1 className="h1" style={{ marginBottom: 0, flex: 1 }}>圈子</h1>
        <button onClick={() => setShowCreate(true)} className="btn" style={{ fontSize: 13 }}>
          + 创建圈子
        </button>
      </div>

      {/* Category filter */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 14, overflowX: 'auto', paddingBottom: 4 }}>
        <button onClick={() => setCategory('')} className="btn-chip"
          style={!category ? { background: 'var(--accent-subtle)', color: 'var(--accent)', borderColor: 'var(--accent)' } : {}}>
          全部
        </button>
        {CATEGORIES.map(c => (
          <button key={c.key} onClick={() => setCategory(c.key)} className="btn-chip"
            style={category === c.key ? { background: 'var(--accent-subtle)', color: 'var(--accent)', borderColor: 'var(--accent)' } : {}}>
            {c.icon} {c.label}
          </button>
        ))}
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="card" style={{ padding: 20, marginBottom: 14 }}>
          <h3 className="h2">创建圈子</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
            <input placeholder="圈子名称" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="input" />
            <input placeholder="标识 (URL, 如 ops-circle)" value={form.slug} onChange={e => setForm({ ...form, slug: e.target.value })} className="input" />
            <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} className="input">
              {CATEGORIES.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
            </select>
            <textarea placeholder="圈子简介" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} className="input" rows={2} />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowCreate(false)} className="btn-secondary">取消</button>
              <button onClick={createCircle} disabled={!form.name || !form.slug} className="btn">创建</button>
            </div>
          </div>
        </div>
      )}

      {/* Circle grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-3)' }}>加载中...</div>
      ) : circles.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-3)' }}>
          暂无圈子 — 创建第一个圈子，聚集同行业的主理人
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(auto-fill, minmax(${isMobile ? '100%' : '280px'}, 1fr))`, gap: 12 }}>
          {circles.map(c => (
            <div key={c.id} className="card" style={{ padding: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                <span style={{ fontWeight: 600, fontSize: 15 }}>{c.name}</span>
                <span className="tag" style={{ background: 'var(--accent-subtle)', color: 'var(--accent)' }}>
                  {catLabel(c.category)}
                </span>
              </div>
              <p style={{ color: 'var(--text-2)', fontSize: 13, marginBottom: 10, lineHeight: 1.6 }}>
                {c.description || '暂无简介'}
              </p>
              <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-3)', marginBottom: 10 }}>
                <span>👥 {c.member_count} 成员</span>
                <span>📝 {c.post_count} 帖子</span>
              </div>
              <button onClick={() => joinCircle(c.id)} className="btn" style={{ width: '100%', fontSize: 13 }}>
                加入圈子
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
