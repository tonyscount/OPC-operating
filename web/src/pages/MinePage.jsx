import { useState, useEffect } from 'react'
import { api } from '../api/client'

export default function MinePage({ onSettings, user }) {
  const [stats, setStats] = useState({})

  useEffect(() => {
    api.getDashboard().then(setStats)
  }, [])

  const name = user?.display_name || user?.username || 'OP'
  return (
    <div style={{ padding: '0 16px 100px' }}>
      {/* Profile card */}
      <div className="card" style={{ padding: 20, marginBottom: 14, textAlign: 'center', marginTop: 12 }}>
        <div style={{ width: 64, height: 64, borderRadius: 18, background: 'var(--accent-subtle)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, fontWeight: 800, margin: '0 auto 10px' }}>{name.slice(0, 2).toUpperCase()}</div>
        <div style={{ fontSize: 18, fontWeight: 700 }}>{name}</div>
        <div style={{ color: 'var(--text-3)', fontSize: 13, marginTop: 2 }}>@{user?.username}</div>
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
        {[
          { label: '用户', value: stats.users || 0 },
          { label: '动态', value: stats.posts || 0 },
          { label: '文档', value: stats.documents || 0 },
          { label: '订单', value: stats.orders || 0 },
        ].map(s => (
          <div key={s.label} className="card" style={{ flex: 1, padding: 14, textAlign: 'center' }}>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{s.value}</div>
            <div className="caption">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Menu */}
      <div className="card" style={{ overflow: 'hidden' }}>
        {[
          { icon: '⚙️', label: 'API 设置', action: onSettings },
          { icon: '🔑', label: '修改密码', action: () => alert('功能开发中') },
          { icon: '📊', label: '运营仪表盘', action: () => {} },
          { icon: '📋', label: '关于 OPC', action: () => alert('OPC Platform v0.1.0') },
        ].map((m, i) => (
          <button key={i} onClick={m.action} style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: 12, padding: '14px 18px',
            background: 'none', border: 'none', borderBottom: i < 3 ? '1px solid var(--border-subtle)' : 'none',
            fontSize: 15, fontFamily: 'var(--font)', color: 'var(--text)', cursor: 'pointer', textAlign: 'left',
          }}>
            <span style={{ fontSize: 18 }}>{m.icon}</span>
            <span style={{ flex: 1 }}>{m.label}</span>
            <span style={{ color: 'var(--text-3)' }}>›</span>
          </button>
        ))}
      </div>
    </div>
  )
}
