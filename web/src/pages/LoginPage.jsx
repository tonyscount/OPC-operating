import { useState } from 'react'
import { api, setToken, setRefreshToken } from '../api/client'

export default function LoginPage({ onLogin }) {
  const [isRegister, setIsRegister] = useState(false)
  const [slug, setSlug] = useState('demo')
  const [tenantName, setTenantName] = useState('')
  const [user, setUser] = useState('admin')
  const [pass, setPass] = useState('admin123456')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault(); setLoading(true); setErr('')
    try {
      if (isRegister) {
        const r = await fetch('/api/v1/auth/register', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tenant_name: tenantName, tenant_slug: slug, username: user, password: pass, display_name: user }),
        })
        if (!r.ok) { const d = await r.json(); throw new Error(d.error?.message || '注册失败') }
        const d = await r.json(); setToken(d.access_token); setRefreshToken(d.refresh_token); onLogin()
      } else {
        const d = await api.login(slug, user, pass); setToken(d.access_token); setRefreshToken(d.refresh_token); onLogin()
      }
    } catch (x) { setErr(x.message) }
    setLoading(false)
  }

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh',
      background: 'linear-gradient(135deg, #F8F9FB 0%, #EEF2FF 100%)',
    }}>
      <form onSubmit={submit} style={{
        width: 400, padding: 44, background: '#fff', borderRadius: 24, border: '1px solid var(--border)',
        boxShadow: '0 8px 40px rgba(0,0,0,.06)',
      }}>
        {/* Brand */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{
            width: 56, height: 56, margin: '0 auto 16px', borderRadius: 16,
            background: 'linear-gradient(135deg, #4F46E5, #818CF8)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 24, color: '#fff', fontWeight: 800,
          }}>OP</div>
          <h1 style={{ fontWeight: 800, fontSize: 26, color: 'var(--text-primary)', letterSpacing: '-.5px' }}>
            OPC Platform
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 4 }}>
            一人公司 · 工业社交 · 知识资产
          </p>
        </div>

        {err && (
          <div style={{ background: 'var(--red-light)', color: 'var(--red)', padding: 10, borderRadius: 12, marginBottom: 16, fontSize: 13 }}>
            {err}
          </div>
        )}

        {isRegister && (
          <input placeholder="组织名称（如：西安OPC）" value={tenantName} onChange={e => setTenantName(e.target.value)} className="input" style={{ marginBottom: 12 }} />
        )}
        <input placeholder={isRegister ? '租户标识（URL，如：xa-opc）' : '租户标识'} value={slug} onChange={e => setSlug(e.target.value)} className="input" style={{ marginBottom: 12 }} />
        <input placeholder="用户名" value={user} onChange={e => setUser(e.target.value)} className="input" style={{ marginBottom: 12 }} />
        <input placeholder="密码" type="password" value={pass} onChange={e => setPass(e.target.value)} className="input" style={{ marginBottom: 20 }} />

        <button type="submit" disabled={loading} className="btn" style={{ width: '100%', height: 46, fontSize: 15 }}>
          {loading ? (isRegister ? '注册中...' : '登录中...') : (isRegister ? '注册并进入' : '进入平台')}
        </button>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16, fontSize: 12 }}>
          <button type="button" onClick={() => setIsRegister(!isRegister)} style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontWeight: 600, fontFamily: 'var(--font)' }}>
            {isRegister ? '已有账号？登录' : '创建新组织'}
          </button>
          {!isRegister && (
            <span style={{ color: 'var(--text-3)' }}>demo / admin / admin123456</span>
          )}
        </div>
      </form>
    </div>
  )
}
