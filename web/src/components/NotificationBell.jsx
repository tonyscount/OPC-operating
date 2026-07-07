import { useState, useEffect, useRef } from 'react'

export default function NotificationBell() {
  const [unread, setUnread] = useState(0)
  const [notifs, setNotifs] = useState([])
  const [show, setShow] = useState(false)
  const ref = useRef(null)

  const load = async () => {
    try {
      const r = await fetch('/api/v1/notifications', { headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` } })
      const d = await r.json(); setNotifs(d.items || [])
      const r2 = await fetch('/api/v1/notifications/unread-count', { headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` } })
      setUnread((await r2.json()).unread || 0)
    } catch (e) {}
  }

  useEffect(() => { load(); const i = setInterval(load, 30000); return () => clearInterval(i) }, [])
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setShow(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const markRead = async (id) => {
    await fetch(`/api/v1/notifications/${id}/read`, { method: 'PATCH', headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` } })
    load()
  }
  const markAll = async () => {
    await fetch('/api/v1/notifications/read-all', { method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` } })
    load()
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={() => { setShow(!show); if (!show) load() }} style={{
        background: show ? 'var(--accent-subtle)' : 'transparent', border: 'none', cursor: 'pointer', fontSize: 14, padding: '6px 10px', borderRadius: 6,
        position: 'relative', display: 'flex', alignItems: 'center', gap: 4,
        color: show ? 'var(--accent)' : 'var(--text-2)', fontFamily: 'var(--font)', fontWeight: show ? 600 : 500, transition: 'all .15s',
      }}>
        🔔
        {unread > 0 && (
          <span style={{
            position: 'absolute', top: -2, right: -2, minWidth: 16, height: 16, borderRadius: 8,
            background: '#DC2626', color: '#fff', fontSize: 10, fontWeight: 700,
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 4px',
          }}>{unread > 99 ? '99+' : unread}</span>
        )}
      </button>

      {show && (
        <div style={{
          position: 'absolute', top: 36, right: 0, width: 340, maxHeight: 400, overflow: 'auto',
          background: '#fff', borderRadius: 10, border: '1px solid var(--border)',
          boxShadow: '0 8px 30px rgba(0,0,0,.1)', zIndex: 200,
        }}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 600, fontSize: 13 }}>通知</span>
            {unread > 0 && <button onClick={markAll} style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 11 }}>全部已读</button>}
          </div>
          {notifs.length === 0 && <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-3)', fontSize: 12 }}>暂无通知</div>}
          {notifs.slice(0, 15).map(n => (
            <div key={n.id} onClick={() => markRead(n.id)} style={{
              padding: '10px 14px', borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer',
              background: n.is_read ? '#fff' : 'var(--accent-subtle)', fontSize: 12,
            }}>
              <div style={{ fontWeight: n.is_read ? 400 : 600 }}>{n.title}</div>
              <div style={{ color: 'var(--text-2)', marginTop: 2 }}>{n.body}</div>
              <div className="caption" style={{ marginTop: 2 }}>
                {n.urgency === 'high' && <span style={{ color: '#DC2626', fontWeight: 600 }}>紧急 · </span>}
                {new Date(n.created_at).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
