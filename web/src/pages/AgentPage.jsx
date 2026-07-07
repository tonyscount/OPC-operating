import { useState, useRef } from 'react'
import { api } from '../api/client'

const AGENTS = [
  { name: 'analyst', label: '分析师', desc: '数据分析与知识检索', color: '#0F766E' },
  { name: 'support_agent', label: '客服', desc: '平台使用指导与问题排查', color: '#0F766E' },
  { name: 'reviewer', label: '审核员', desc: '内容审核与合规检查', color: '#0F766E' },
  { name: 'judge', label: '评审', desc: '多 Agent 综合裁决', color: '#0F766E' },
]

export default function AgentPage({ isMobile }) {
  const [agent, setAgent] = useState('analyst'); const [input, setInput] = useState('')
  const [messages, setMessages] = useState([]); const [loading, setLoading] = useState(false)
  const chatRef = useRef(null)

  const current = AGENTS.find(a => a.name === agent)

  const run = async () => {
    if (!input.trim() || loading) return
    setMessages(prev => [...prev, { role: 'user', content: input, agent }])
    setInput(''); setLoading(true)
    try {
      const r = await api.runAgent(agent, input)
      setMessages(prev => [...prev, { role: 'assistant', content: r.output || 'Agent 执行完成', agent, steps: r.steps, stopped: r.stopped }])
    } catch (e) { setMessages(prev => [...prev, { role: 'assistant', content: '执行失败: ' + e.message, agent }]) }
    setLoading(false); setTimeout(() => chatRef.current?.scrollTo(0, chatRef.current.scrollHeight), 100)
  }

  if (isMobile) return <MobileAgentView {...{ agent, setAgent, input, setInput, messages, loading, run }} />

  const col = '220px 1fr'
  return (
    <div>
      <div className="h1" style={{ marginBottom: 16 }}>Agent 对话</div>
      <div style={{ display: 'grid', gridTemplateColumns: col, gap: 14, height: isMobile ? 'auto' : 'calc(100vh - 120px)' }}>
        <div className="card" style={{ padding: 16, overflow: 'auto' }}>
          <div className="h2" style={{ marginBottom: 10 }}>Agent</div>
          {AGENTS.map(a => (
            <button key={a.name} onClick={() => setAgent(a.name)} className="card" style={{
              width: '100%', padding: 12, marginBottom: 6, textAlign: 'left', cursor: 'pointer', border: 'none',
              background: agent === a.name ? 'var(--accent-subtle)' : '#fff',
              borderLeft: agent === a.name ? '3px solid var(--accent)' : '3px solid transparent',
              transition: 'all .15s',
            }}>
              <div style={{ fontWeight: 600, fontSize: 13, color: agent === a.name ? 'var(--accent)' : 'var(--text)' }}>{a.label}</div>
              <div className="caption" style={{ marginTop: 2 }}>{a.desc}</div>
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card" style={{ padding: '10px 16px', marginBottom: 10, flexShrink: 0 }}>
            <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--accent)' }}>{current?.label} Agent</span>
            <span className="caption" style={{ marginLeft: 8 }}>{current?.desc}</span>
          </div>

          <div ref={chatRef} className="card no-scroll" style={{ flex: 1, padding: 20, overflow: 'auto', marginBottom: 10 }}>
            {messages.length === 0 && <div style={{ textAlign: 'center', color: 'var(--text-3)', paddingTop: 40, fontSize: 13 }}>向 {current?.label} Agent 提问</div>}
            {messages.map((m, i) => (
              <div key={i} style={{ marginBottom: 14 }}>
                {m.role === 'user' ? (
                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <div style={{ background: 'var(--accent-subtle)', color: 'var(--accent)', padding: '8px 16px', borderRadius: '12px 12px 4px 12px', maxWidth: '80%', fontSize: 13 }}>{m.content}</div>
                  </div>
                ) : (
                  <div style={{ fontSize: 13, lineHeight: 1.8, color: 'var(--text)', whiteSpace: 'pre-wrap' }}>
                    {m.content}
                    {m.steps && <span className="caption" style={{ marginLeft: 8 }}>· {m.steps} 步</span>}
                    {m.stopped && <span className="tag tag-warn" style={{ marginLeft: 8 }}>已中断</span>}
                  </div>
                )}
              </div>
            ))}
            {loading && <div style={{ color: 'var(--accent)', fontSize: 13 }}>Agent 思考中...</div>}
          </div>

          <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
            <input placeholder={`向 ${current?.label} 提问...`} value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && run()} className="input" style={{ flex: 1 }} />
            <button onClick={run} disabled={loading} className="btn">{loading ? '...' : '→'}</button>
          </div>
        </div>
      </div>
    </div>
  )
}

function MobileAgentView({ agent, setAgent, input, setInput, messages, loading, run }) {
  const current = AGENTS.find(a => a.name === agent)
  const chatRef = { current: null }
  return (
    <div style={{ padding: '0 16px 80px' }}>
      {/* Agent picker — horizontal scroll */}
      <div style={{ display: 'flex', gap: 6, padding: '12px 0', overflowX: 'auto' }} className="no-scroll">
        {AGENTS.map(a => (
          <button key={a.name} onClick={() => setAgent(a.name)} style={{
            padding: '8px 16px', borderRadius: 20, whiteSpace: 'nowrap', flexShrink: 0,
            border: agent === a.name ? '2px solid var(--accent)' : '1px solid var(--border)',
            background: agent === a.name ? 'var(--accent-subtle)' : '#fff',
            color: agent === a.name ? 'var(--accent)' : 'var(--text-2)',
            fontFamily: 'var(--font)', fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}>{a.label}</button>
        ))}
      </div>

      {/* Chat area */}
      <div className="card" style={{ padding: 16, marginBottom: 10 }}>
        <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--accent)', marginBottom: 10 }}>{current?.label} · {current?.desc}</div>
        <div ref={chatRef} style={{ maxHeight: '50vh', overflow: 'auto', marginBottom: 10 }}>
          {messages.length === 0 && <div style={{ textAlign: 'center', color: 'var(--text-3)', padding: 20, fontSize: 14 }}>向 {current?.label} 提问</div>}
          {messages.map((m, i) => (
            <div key={i} style={{ marginBottom: 10 }}>
              {m.role === 'user' ? (
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <div style={{ background: 'var(--accent-subtle)', color: 'var(--accent)', padding: '10px 16px', borderRadius: '16px 16px 4px 16px', maxWidth: '85%', fontSize: 14 }}>{m.content}</div>
                </div>
              ) : (
                <div style={{ fontSize: 14, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                  {m.content}
                  {m.steps && <span className="caption" style={{ marginLeft: 8 }}>· {m.steps} 步</span>}
                </div>
              )}
            </div>
          ))}
          {loading && <div style={{ color: 'var(--accent)', fontSize: 13 }}>思考中...</div>}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input placeholder="输入..." value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && run()} className="input" style={{ flex: 1, fontSize: 15 }} />
          <button onClick={run} disabled={loading} className="btn" style={{ minWidth: 48, height: 44 }}>→</button>
        </div>
      </div>
    </div>
  )
}
