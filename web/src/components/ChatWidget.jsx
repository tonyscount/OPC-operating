import { useState, useEffect, useRef } from 'react'

export default function ChatWidget() {
  const [open, setOpen] = useState(false)
  const [convs, setConvs] = useState([])
  const [activeConv, setActiveConv] = useState(null)
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [ws, setWs] = useState(null)
  const msgRef = useRef(null)

  const token = () => localStorage.getItem('opc_token')

  const loadConvs = async () => {
    try {
      const r = await fetch('/api/v1/conversations', { headers: { Authorization: `Bearer ${token()}` } })
      setConvs((await r.json()).items || [])
    } catch (e) {}
  }

  const loadMessages = async (convId) => {
    try {
      const r = await fetch(`/api/v1/conversations/${convId}/messages`, { headers: { Authorization: `Bearer ${token()}` } })
      setMessages((await r.json()).items || [])
    } catch (e) {}
  }

  useEffect(() => { if (open) loadConvs() }, [open])
  useEffect(() => {
    if (!activeConv) return
    loadMessages(activeConv)
    // Connect WebSocket
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const socket = new WebSocket(`${protocol}//${host}/ws?token=${token()}`)
      socket.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data)
          if (d.type === 'private_message') setMessages(p => [...p, { sender_id: d.from, content: d.content, created_at: new Date().toISOString() }])
        } catch (e) {}
      }
      setWs(socket)
      return () => socket.close()
    } catch (e) {}
  }, [activeConv])

  useEffect(() => { msgRef.current?.scrollTo(0, msgRef.current.scrollHeight) }, [messages])

  const send = () => {
    if (!text.trim() || !ws || !activeConv) return
    const msg = { type: 'private_message', to: activeConv, content: text.trim(), conversation_id: activeConv, tenant_id: '', timestamp: new Date().toISOString() }
    ws.send(JSON.stringify(msg))
    setMessages(p => [...p, { sender_id: 'me', content: text.trim(), created_at: new Date().toISOString() }])
    setText('')
  }

  return (
    <>
      <button onClick={() => setOpen(!open)} style={{ background: open ? 'var(--accent-subtle)' : 'transparent', border: 'none', cursor: 'pointer', fontSize: 14, padding: '6px 10px', borderRadius: 6, color: open ? 'var(--accent)' : 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 4, fontFamily: 'var(--font)', fontWeight: open ? 600 : 500, transition: 'all .15s' }}>
        <i className="iconfont icon-siliao" style={{ fontSize: 18 }} />
      </button>

      {open && (
        <div style={{ position: 'fixed', bottom: 20, right: 20, width: 360, height: 480, background: '#fff', borderRadius: 12, border: '1px solid var(--border)', boxShadow: '0 8px 40px rgba(0,0,0,.12)', display: 'flex', flexDirection: 'column', zIndex: 500 }}>
          {/* Header */}
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="h2" style={{ margin: 0 }}>消息</span>
            <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, color: 'var(--text-3)' }}>×</button>
          </div>

          {/* Conv list or messages */}
          {!activeConv ? (
            <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
              {convs.length === 0 && <div className="caption" style={{ textAlign: 'center', padding: 20 }}>暂无会话</div>}
              {convs.map(c => (
                <button key={c.id} onClick={() => setActiveConv(c.id)} style={{ width: '100%', textAlign: 'left', padding: '10px 14px', background: 'none', border: 'none', cursor: 'pointer', borderRadius: 8, borderBottom: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{c.title || '私聊'}</div>
                  <div className="caption" style={{ marginTop: 2 }}>{c.last_message?.slice(0, 60) || '新会话'}</div>
                  {c.unread > 0 && <span style={{ background: '#DC2626', color: '#fff', borderRadius: 10, padding: '1px 6px', fontSize: 10 }}>{c.unread}</span>}
                </button>
              ))}
            </div>
          ) : (
            <>
              <button onClick={() => setActiveConv(null)} className="btn-ghost" style={{ margin: '8px 12px', alignSelf: 'flex-start', fontSize: 12 }}>← 返回</button>
              <div ref={msgRef} style={{ flex: 1, overflow: 'auto', padding: '0 14px' }}>
                {messages.map((m, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: m.sender_id === 'me' ? 'flex-end' : 'flex-start', marginBottom: 8 }}>
                    <div style={{ maxWidth: '75%', padding: '8px 14px', borderRadius: 12, fontSize: 13, lineHeight: 1.5,
                      background: m.sender_id === 'me' ? 'var(--accent-subtle)' : 'var(--bg)',
                      color: m.sender_id === 'me' ? 'var(--accent)' : 'var(--text)',
                    }}>
                      {m.content}
                      <div className="caption" style={{ marginTop: 2, fontSize: 9 }}>{new Date(m.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 8, padding: '8px 14px', borderTop: '1px solid var(--border-subtle)' }}>
                <input placeholder="输入消息..." value={text} onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') send() }} className="input" style={{ flex: 1, fontSize: 12 }} />
                <button onClick={send} className="btn" style={{ height: 34, fontSize: 12, padding: '0 14px' }}>发送</button>
              </div>
            </>
          )}
        </div>
      )}
    </>
  )
}
