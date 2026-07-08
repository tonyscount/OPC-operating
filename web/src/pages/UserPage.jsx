import { useState, useEffect } from 'react'
import { api } from '../api/client'

export default function UserPage({ userId, onClose }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getBusinessCard(userId)
      .then(d => { setProfile(d); setLoading(false) })
  }, [userId])

  const follow = async () => {
    await api.followUser(userId)
    setProfile(prev => ({ ...prev, is_following: true }))
  }

  if (loading) return <div className="card" style={{ padding: 24, textAlign: 'center', color: 'var(--text-3)' }}>加载中...</div>

  const u = profile?.user || {}
  const skills = profile?.skills || []
  const devices = profile?.devices || []
  const stats = profile?.stats || {}

  return (
    <div className="card" style={{ padding: 24, maxWidth: 500 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <button onClick={onClose} className="btn-secondary" style={{ fontSize: 12 }}>← 返回</button>
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={follow} className="btn" style={{ fontSize: 12, padding: '4px 14px' }}>
            {profile?.is_following ? '已关注' : '+ 关注'}
          </button>
          <button onClick={async () => {
            await api.sendFriendRequest(userId)
            alert('好友申请已发送')
          }} className="btn-secondary" style={{ fontSize: 12, padding: '4px 14px' }}>+好友</button>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
        <div style={{ width: 56, height: 56, borderRadius: 14, background: 'var(--accent-subtle)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, fontWeight: 800 }}>
          {(u.display_name || u.username || 'OP').slice(0, 2).toUpperCase()}
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 18 }}>{u.display_name || u.username}</div>
          <div style={{ color: 'var(--text-3)', fontSize: 13 }}>@{u.username}</div>
        </div>
      </div>

      {profile?.status?.text && (
        <div style={{ padding: '8px 12px', background: 'var(--accent-subtle)', borderRadius: 8, marginBottom: 14, fontSize: 13 }}>
          {profile.status.emoji} {profile.status.text}
        </div>
      )}

      <div style={{ display: 'flex', gap: 20, marginBottom: 16 }}>
        {[{ label: '关注', value: stats.following || 0 }, { label: '粉丝', value: stats.followers || 0 }, { label: '设备', value: stats.devices || 0 }].map(s => (
          <div key={s.label} style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{s.value}</div>
            <div className="caption">{s.label}</div>
          </div>
        ))}
      </div>

      {skills.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div className="caption" style={{ fontWeight: 600, marginBottom: 6 }}>技能标签</div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {skills.map(s => <span key={s.name} className="tag tag-accent">{s.name}</span>)}
          </div>
        </div>
      )}

      {devices.length > 0 && (
        <div>
          <div className="caption" style={{ fontWeight: 600, marginBottom: 6 }}>设备</div>
          {devices.map(d => (
            <div key={d.id} style={{ padding: '6px 0', borderBottom: '1px solid var(--border-subtle)', fontSize: 13 }}>
              <span style={{ fontWeight: 500 }}>{d.name}</span>
              <span className="caption" style={{ marginLeft: 8 }}>{d.ip_address} · {d.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
