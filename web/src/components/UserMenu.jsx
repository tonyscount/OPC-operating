import { useState, useRef, useEffect } from 'react'
import { clearToken } from '../api/client'

export default function UserMenu({ user, onSettings, onLogout }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const name = user?.display_name || user?.username || 'OP'
  const initials = name.slice(0, 2).toUpperCase()

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={() => setOpen(!open)} style={{
        width: 34, height: 34, borderRadius: 10,
        background: 'var(--accent-subtle)', color: 'var(--accent)',
        border: '1px solid var(--border)', cursor: 'pointer',
        fontSize: 13, fontWeight: 700, fontFamily: 'var(--font)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        transition: 'all .15s',
      }}>
        {initials}
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: 42, right: 0, width: 200,
          background: '#fff', borderRadius: 10, border: '1px solid var(--border)',
          boxShadow: '0 8px 30px rgba(0,0,0,.1)', overflow: 'hidden', zIndex: 200,
        }}>
          {/* User info */}
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
            <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)' }}>{name}</div>
            <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 2 }}>{user?.username} · {user?.roles?.[0] || '成员'}</div>
          </div>

          {/* Actions */}
          <button onClick={() => { onSettings(); setOpen(false) }} style={menuItem}>
            <span>⚙</span> API 设置
          </button>
          <button onClick={() => { clearToken(); onLogout(); setOpen(false) }} style={menuItem}>
            <span>↩</span> 退出登录
          </button>
        </div>
      )}
    </div>
  )
}

const menuItem = {
  width: '100%', display: 'flex', alignItems: 'center', gap: 8,
  padding: '10px 16px', background: 'none', border: 'none',
  fontSize: 13, color: 'var(--text-2)', fontFamily: 'var(--font)',
  cursor: 'pointer', transition: 'background .1s',
}
