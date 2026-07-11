import { useState, useRef, useEffect } from 'react'
import { api } from '../api/client'

// Emoji fallback (used when API doesn't return emoji)
const fallbackEmoji = (name) => {
  const m = { '分析师':'📊','客服助手':'🎧','审核员':'🛡️','评审员':'⚖️','架构师':'🏗️','代码审查员':'👁️','运维工程师':'⚙️','内容创作者':'✍️','产品经理':'🧭','安全工程师':'🗡️','SEO优化师':'🔎','项目经理':'📋','财务分析师':'💰','商业策略师':'♟️','数据分析师':'📐','UX研究员':'🔬','测试工程师':'🎭','客户顾问':'🗺️','招聘专员':'🎯','法务顾问':'⚖️','供应链专家':'🔗','AI工程师':'🤖','企业培训师':'📚','前端工程师':'🖥️' }
  return m[name] || '🤖'
}

export default function AgentPage({ isMobile }) {
  const [agents, setAgents] = useState([])
  const [agent, setAgent] = useState('')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const chatRef = useRef(null)

  // Fetch agents from API on mount
  useEffect(() => {
    api.listAgents().then(data => {
      const list = (data.agents || []).map(a => ({
        name: a.name,
        emoji: a.emoji || fallbackEmoji(a.name),
        desc: a.description || a.role_prompt?.slice(0, 80) || '',
        tools: a.tools?.length || 0,
      }))
      setAgents(list)
      if (list.length > 0 && !agent) setAgent(list[0].name)
    }).catch(() => {
      // Fallback if API fails
      const fallback = [
        { name:'分析师', emoji:'📊', desc:'社群数据与活动策划', tools:5 },
        { name:'客服助手', emoji:'🎧', desc:'问题解答与转人工', tools:1 },
        { name:'审核员', emoji:'🛡️', desc:'内容合规审核', tools:1 },
        { name:'评审员', emoji:'⚖️', desc:'多Agent综合裁判', tools:1 },
      ]
      setAgents(fallback)
      setAgent(fallback[0].name)
    })
  }, [])

  const current = agents.find(a => a.name === agent)

  const run = async () => {
    if (!input.trim() || loading || !agent) return
    setMessages(prev => [...prev, { role: 'user', content: input, agent }])
    setInput(''); setLoading(true)
    try {
      const r = await api.runAgent(agent, input)
      setMessages(prev => [...prev, { role: 'assistant', content: r.output || 'Agent 执行完成', agent, steps: r.steps, stopped: r.stopped }])
    } catch (e) { setMessages(prev => [...prev, { role: 'assistant', content: '执行失败: ' + e.message, agent }]) }
    setLoading(false); setTimeout(() => chatRef.current?.scrollTo(0, chatRef.current.scrollHeight), 100)
  }

  if (isMobile) return <MobileAgentView {...{ agents, agent, setAgent, input, setInput, messages, loading, run }} />

  const col = '240px 1fr'
  return (
    <div>
      <div className="h1" style={{ marginBottom: 16 }}>Agent 对话 · {agents.length} 个可用</div>
      <div style={{ display: 'grid', gridTemplateColumns: col, gap: 14, height: 'calc(100vh - 120px)' }}>
        {/* Agent list */}
        <div className="card" style={{ padding: 16, overflow: 'auto' }}>
          <div className="h2" style={{ marginBottom: 10 }}>选择 Agent</div>
          {agents.map(a => (
            <button key={a.name} onClick={() => setAgent(a.name)} className="card" style={{
              width: '100%', padding: 12, marginBottom: 6, textAlign: 'left', cursor: 'pointer', border: 'none',
              background: agent === a.name ? 'var(--accent-subtle)' : '#fff',
              borderLeft: agent === a.name ? '3px solid var(--accent)' : '3px solid transparent',
              transition: 'all .15s',
            }}>
              <div style={{ fontWeight: 600, fontSize: 13, color: agent === a.name ? 'var(--accent)' : 'var(--text)' }}>
                {a.emoji} {a.name}
              </div>
              <div className="caption" style={{ marginTop: 2, fontSize: 11 }}>{a.desc?.slice(0, 60)}</div>
            </button>
          ))}
        </div>

        {/* Chat panel */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card" style={{ padding: '10px 16px', marginBottom: 10, flexShrink: 0 }}>
            <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--accent)' }}>{current?.emoji} {current?.name}</span>
            <span className="caption" style={{ marginLeft: 8 }}>{current?.desc?.slice(0, 70)}</span>
          </div>

          <div ref={chatRef} className="card no-scroll" style={{ flex: 1, padding: 20, overflow: 'auto', marginBottom: 10 }}>
            {messages.length === 0 && <div style={{ textAlign: 'center', color: 'var(--text-3)', paddingTop: 40, fontSize: 13 }}>向 {current?.name} 提问</div>}
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
            <input placeholder={`向 ${current?.name || 'Agent'} 提问...`} value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && run()} className="input" style={{ flex: 1 }} />
            <button onClick={run} disabled={loading || !agent} className="btn">{loading ? '...' : '→'}</button>
          </div>
        </div>
      </div>
    </div>
  )
}

function MobileAgentView({ agents, agent, setAgent, input, setInput, messages, loading, run }) {
  const current = agents.find(a => a.name === agent)
  return (
    <div style={{ padding: '0 16px 80px' }}>
      {/* Agent picker — horizontal scroll */}
      <div style={{ display: 'flex', gap: 6, padding: '12px 0', overflowX: 'auto' }} className="no-scroll">
        {agents.map(a => (
          <button key={a.name} onClick={() => setAgent(a.name)} style={{
            padding: '8px 16px', borderRadius: 20, whiteSpace: 'nowrap', flexShrink: 0,
            border: agent === a.name ? '2px solid var(--accent)' : '1px solid var(--border)',
            background: agent === a.name ? 'var(--accent-subtle)' : '#fff',
            color: agent === a.name ? 'var(--accent)' : 'var(--text-2)',
            fontFamily: 'var(--font)', fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}>{a.emoji} {a.name}</button>
        ))}
      </div>

      {/* Chat area */}
      <div className="card" style={{ padding: 16, marginBottom: 10 }}>
        <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--accent)', marginBottom: 10 }}>{current?.emoji} {current?.name}</div>
        <div ref={{}} style={{ maxHeight: '50vh', overflow: 'auto', marginBottom: 10 }}>
          {messages.length === 0 && <div style={{ textAlign: 'center', color: 'var(--text-3)', padding: 20, fontSize: 14 }}>向 {current?.name} 提问</div>}
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
