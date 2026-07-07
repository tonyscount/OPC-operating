import { useState, useEffect } from 'react'
import { isLoggedIn, clearToken, api } from './api/client'
import LoginPage from './pages/LoginPage'
import KnowledgePage from './pages/KnowledgePage'
import SocialPage from './pages/SocialPage'
import AgentPage from './pages/AgentPage'
import SkillPage from './pages/SkillPage'
import DevicesPage from './pages/DevicesPage'
import OpsPage from './pages/OpsPage'
import DataPage from './pages/DataPage'
import SettingsModal from './components/SettingsModal'
import MinePage from './pages/MinePage'
import UserMenu from './components/UserMenu'
import NotificationBell from './components/NotificationBell'
import ChatWidget from './components/ChatWidget'

const TABS = [
  { key: 'knowledge', label: '知识库' },
  { key: 'social', label: '社群' },
  { key: 'skill', label: 'Skills' },
  { key: 'agent', label: 'Agent' },
  { key: 'devices', label: '设备' },
  { key: 'data', label: '数据' },
  { key: 'ops', label: '运营' },
]

export default function App() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn())
  const [page, setPage] = useState('knowledge')
  const [user, setUser] = useState(null)
  const [width, setWidth] = useState(window.innerWidth)
  const [showSettings, setShowSettings] = useState(false)
  const isMobile = width < 768

  useEffect(() => {
    const onResize = () => setWidth(window.innerWidth)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  useEffect(() => {
    if (loggedIn) api.me().then(setUser).catch(() => { clearToken(); setLoggedIn(false) })
  }, [loggedIn])

  if (!loggedIn) return <LoginPage onLogin={() => setLoggedIn(true)} />

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      {/* Header */}
      {isMobile ? (
        <header style={{ background: '#fff', borderBottom: '1px solid var(--border)', padding: '10px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'sticky', top: 0, zIndex: 100 }}>
          <span style={{ fontWeight: 700, fontSize: 17, color: 'var(--text)' }}>OPC</span>
          <div style={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <ChatWidget />
            <NotificationBell />
            <UserMenu user={user} onSettings={() => setShowSettings(true)} onLogout={() => setLoggedIn(false)} />
          </div>
        </header>
      ) : (
        <header style={{
          background: '#fff', borderBottom: '1px solid var(--border)', height: 52,
          padding: '0 28px', display: 'flex', alignItems: 'center', gap: 2,
          position: 'sticky', top: 0, zIndex: 100,
        }}>
          <span style={{ fontWeight: 700, fontSize: 16, color: 'var(--text)', letterSpacing: '-.2px', marginRight: 28 }}>OPC Platform</span>
          <div style={{ position: 'relative', flex: 1, maxWidth: 240 }}>
            <input placeholder="🔍 搜索帖子、文档、用户..." className="input" style={{ padding: '6px 10px 6px 30px', fontSize: 12, background: 'var(--bg)' }}
              onKeyDown={async (e) => {
                if (e.key === 'Enter' && e.target.value.trim()) {
                  const q = e.target.value.trim()
                  const r = await fetch('/api/v1/search', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('opc_token')}` }, body: JSON.stringify({ query: q, page: 1, page_size: 10 }) })
                  const d = await r.json(); const items = d.items || []
                  alert(items.length === 0 ? '未找到结果' : `找到 ${d.total} 条:\n${items.map(i => `· [${i.source_type}] ${(i.title||'').slice(0,50)}`).join('\n')}`)
                }
              }} />
          </div>
          {TABS.map(t => (
            <button key={t.key} onClick={() => setPage(t.key)} style={{
              background: page === t.key ? 'var(--accent-subtle)' : 'transparent',
              color: page === t.key ? 'var(--accent)' : 'var(--text-2)',
              border: 'none', padding: '6px 14px', borderRadius: 6, cursor: 'pointer',
              fontSize: 13, fontWeight: page === t.key ? 600 : 500, fontFamily: 'var(--font)',
              transition: 'all .15s',
            }}>{t.label}</button>
          ))}
          <div style={{ flex: 1 }} />
          <span style={{ color: 'var(--border)', margin: '0 2px' }}>|</span>
          <ChatWidget />
          <NotificationBell />
          <UserMenu user={user} onSettings={() => setShowSettings(true)} onLogout={() => setLoggedIn(false)} />
        </header>
      )}

      <main style={{ padding: isMobile ? 16 : 24 }}>
        {page === 'knowledge' && <KnowledgePage isMobile={isMobile} />}
        {page === 'social' && <SocialPage isMobile={isMobile} />}
        {page === 'skill' && <SkillPage isMobile={isMobile} />}
        {page === 'agent' && <AgentPage isMobile={isMobile} />}
        {page === 'devices' && <DevicesPage />}
        {page === 'data' && <DataPage />}
        {page === 'profile' && <MinePage user={user} onSettings={() => setShowSettings(true)} />}
        {page === 'ops' && <OpsPage />}
      </main>

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}

      {isMobile && (
        <nav style={{
          position: 'fixed', bottom: 0, left: 0, right: 0, background: '#fff',
          borderTop: '1px solid var(--border)', display: 'flex', zIndex: 200,
          paddingBottom: 'env(safe-area-inset-bottom)',
        }}>
          {[
            { key: 'social', icon: '💬', label: '社群' },
            { key: 'knowledge', icon: '📚', label: '知识库' },
            { key: 'agent', icon: '🤖', label: 'Agent' },
            { key: 'profile', icon: '👤', label: '我的' },
          ].map(t => (
            <button key={t.key} onClick={() => setPage(t.key)} style={{
              flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
              padding: '8px 0 6px', border: 'none', background: 'transparent',
              color: page === t.key ? 'var(--accent)' : 'var(--text-3)',
              cursor: 'pointer', fontFamily: 'var(--font)', fontSize: 10, fontWeight: page === t.key ? 600 : 400,
            }}>
              <span style={{ fontSize: 20 }}>{t.icon}</span>
              <span>{t.label}</span>
            </button>
          ))}
        </nav>
      )}
      {!isMobile && (
        <nav className="card" style={{
          position: 'fixed', bottom: 12, left: '50%', transform: 'translateX(-50%)',
          display: 'flex', gap: 2, padding: '5px 8px', borderRadius: 16, zIndex: 200,
        }}>
          {TABS.map(t => (
            <button key={t.key} onClick={() => setPage(t.key)} style={{
              background: page === t.key ? 'var(--accent-subtle)' : 'transparent',
              color: page === t.key ? 'var(--accent)' : 'var(--text-2)',
              border: 'none', padding: '6px 12px', borderRadius: 12, cursor: 'pointer',
              fontSize: 12, fontWeight: page === t.key ? 600 : 500, fontFamily: 'var(--font)',
            }}>{t.icon} {t.label}</button>
          ))}
        </nav>
      )}
    </div>
  )
}
