import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom'
import { isLoggedIn, api } from './api/client'
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
  { key: 'knowledge', label: '知识库', path: '/knowledge' },
  { key: 'social', label: '社群', path: '/social' },
  { key: 'skill', label: 'Skills', path: '/skills' },
  { key: 'agent', label: 'Agent', path: '/agent' },
  { key: 'devices', label: '设备', path: '/devices' },
  { key: 'data', label: '数据', path: '/data' },
  { key: 'ops', label: '运营', path: '/ops' },
]

const MOBILE_TABS = [
  { key: 'social', icon: '💬', label: '社群', path: '/social' },
  { key: 'knowledge', icon: '📚', label: '知识库', path: '/knowledge' },
  { key: 'agent', icon: '🤖', label: 'Agent', path: '/agent' },
  { key: 'profile', icon: '👤', label: '我的', path: '/profile' },
]

function useCurrentTab() {
  const location = useLocation()
  const all = [...TABS, ...MOBILE_TABS, { path: '/profile' }]
  const match = all.find(t => location.pathname.startsWith(t.path))
  return match ? match.key : 'knowledge'
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  )
}

function AppContent() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn())
  const [user, setUser] = useState(null)
  const [width, setWidth] = useState(window.innerWidth)
  const [showSettings, setShowSettings] = useState(false)
  const isMobile = width < 768
  const currentTab = useCurrentTab()
  const navigate = useNavigate()

  useEffect(() => {
    const onResize = () => setWidth(window.innerWidth)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  useEffect(() => {
    if (loggedIn) api.me().then(setUser).catch(() => { api.logout(); setLoggedIn(false) })
  }, [loggedIn])

  if (!loggedIn) return <LoginPage onLogin={() => setLoggedIn(true)} />

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      {/* Header */}
      {isMobile ? (
        <header style={{ background: '#fff', borderBottom: '1px solid var(--border)', padding: '10px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'sticky', top: 0, zIndex: 100 }}>
          <Link to="/" style={{ fontWeight: 700, fontSize: 17, color: 'var(--text)', textDecoration: 'none' }}>OPC</Link>
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
          <Link to="/" style={{ fontWeight: 700, fontSize: 16, color: 'var(--text)', letterSpacing: '-.2px', marginRight: 28, textDecoration: 'none' }}>OPC Platform</Link>
          <div style={{ position: 'relative', flex: 1, maxWidth: 240 }}>
            <input placeholder="🔍 搜索帖子、文档、用户..." className="input" style={{ padding: '6px 10px 6px 30px', fontSize: 12, background: 'var(--bg)' }}
              onKeyDown={async (e) => {
                if (e.key === 'Enter' && e.target.value.trim()) {
                  const q = e.target.value.trim()
                  try {
                    const d = await api.search(q)
                    const items = d.items || []
                    navigate(`/search?q=${encodeURIComponent(q)}`)
                    alert(items.length === 0 ? '未找到结果' : `找到 ${d.total} 条:\n${items.map(i => `· [${i.source_type}] ${(i.title||'').slice(0,50)}`).join('\n')}`)
                  } catch (err) { alert('搜索失败: ' + err.message) }
                }
              }} />
          </div>
          {TABS.map(t => (
            <Link key={t.key} to={t.path} style={{
              background: currentTab === t.key ? 'var(--accent-subtle)' : 'transparent',
              color: currentTab === t.key ? 'var(--accent)' : 'var(--text-2)',
              border: 'none', padding: '6px 14px', borderRadius: 6, cursor: 'pointer',
              fontSize: 13, fontWeight: currentTab === t.key ? 600 : 500, fontFamily: 'var(--font)',
              transition: 'all .15s', textDecoration: 'none',
            }}>{t.label}</Link>
          ))}
          <div style={{ flex: 1 }} />
          <span style={{ color: 'var(--border)', margin: '0 2px' }}>|</span>
          <ChatWidget />
          <NotificationBell />
          <UserMenu user={user} onSettings={() => setShowSettings(true)} onLogout={() => setLoggedIn(false)} />
        </header>
      )}

      <main style={{ padding: isMobile ? 16 : 24 }}>
        <Routes>
          <Route path="/" element={<KnowledgePage isMobile={isMobile} />} />
          <Route path="/knowledge" element={<KnowledgePage isMobile={isMobile} />} />
          <Route path="/social" element={<SocialPage isMobile={isMobile} />} />
          <Route path="/skills" element={<SkillPage isMobile={isMobile} />} />
          <Route path="/agent" element={<AgentPage isMobile={isMobile} />} />
          <Route path="/devices" element={<DevicesPage />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="/ops" element={<OpsPage />} />
          <Route path="/profile" element={<MinePage user={user} onSettings={() => setShowSettings(true)} />} />
          <Route path="*" element={<KnowledgePage isMobile={isMobile} />} />
        </Routes>
      </main>

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}

      {isMobile && (
        <nav style={{
          position: 'fixed', bottom: 0, left: 0, right: 0, background: '#fff',
          borderTop: '1px solid var(--border)', display: 'flex', zIndex: 200,
          paddingBottom: 'env(safe-area-inset-bottom)',
        }}>
          {MOBILE_TABS.map(t => (
            <Link key={t.key} to={t.path} style={{
              flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
              padding: '8px 0 6px', border: 'none', background: 'transparent',
              color: currentTab === t.key ? 'var(--accent)' : 'var(--text-3)',
              cursor: 'pointer', fontFamily: 'var(--font)', fontSize: 10, fontWeight: currentTab === t.key ? 600 : 400,
              textDecoration: 'none',
            }}>
              <span style={{ fontSize: 20 }}>{t.icon}</span>
              <span>{t.label}</span>
            </Link>
          ))}
        </nav>
      )}
      {!isMobile && (
        <nav className="card" style={{
          position: 'fixed', bottom: 12, left: '50%', transform: 'translateX(-50%)',
          display: 'flex', gap: 2, padding: '5px 8px', borderRadius: 16, zIndex: 200,
        }}>
          {TABS.map(t => (
            <Link key={t.key} to={t.path} style={{
              background: currentTab === t.key ? 'var(--accent-subtle)' : 'transparent',
              color: currentTab === t.key ? 'var(--accent)' : 'var(--text-2)',
              border: 'none', padding: '6px 12px', borderRadius: 12, cursor: 'pointer',
              fontSize: 12, fontWeight: currentTab === t.key ? 600 : 500, fontFamily: 'var(--font)',
              textDecoration: 'none',
            }}>{t.icon} {t.label}</Link>
          ))}
        </nav>
      )}
    </div>
  )
}
