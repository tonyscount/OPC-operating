import { useState, useEffect, useRef } from 'react'
import { api } from '../api/client'

export default function KnowledgePage({ isMobile }) {
  const [docs, setDocs] = useState([]); const [stats, setStats] = useState({})
  const [expiring, setExpiring] = useState([]); const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState(''); const [role, setRole] = useState('member')
  const [loading, setLoading] = useState(false); const [agentMode, setAgentMode] = useState(false)
  const [thinkingSteps, setThinkingSteps] = useState([]); const [skills, setSkills] = useState([])
  const [showUpload, setShowUpload] = useState(false); const [uploadTitle, setUploadTitle] = useState('')
  const [docDetail, setDocDetail] = useState(null)
  const chatRef = useRef(null); const uploadRef = useRef(null)

  const load = () => {
    api.getDocuments({ page_size: 20 }).then(d => setDocs(d.items || []))
    api.getStats().then(setStats)
    api.getExpiringDocuments().then(d => setExpiring(d.items || []))
  }
  useEffect(() => { load()
    api.getSkills().then(d => setSkills(d.skills || []))
  }, [])

  const ask = async () => {
    if (!question.trim()) return; setLoading(true); setAnswer(''); setThinkingSteps([])
    try {
      if (agentMode) { const r = await api.runAgent('analyst', question); if (r.messages) setThinkingSteps(r.messages); setAnswer(r.output || 'Agent 执行完成') }
      else { const r = await api.askQuestion(question, role); setAnswer(r.answer || 'AI 不可用 (需 API Key)'); if (r.sources?.length) setAnswer(p => p + '\n\n—\n' + r.sources.map(s => s.document_title).join(' · ')) }
    } catch (e) { setAnswer('请求失败: ' + e.message) }
    setLoading(false); setTimeout(() => chatRef.current?.scrollTo(0, chatRef.current.scrollHeight), 100)
  }
  const handleUpload = async () => { if (!uploadTitle || !uploadRef.current?.innerText) return; await api.uploadText(uploadTitle, uploadRef.current.innerText); setShowUpload(false); setUploadTitle(''); uploadRef.current.innerText = ''; load() }
  const handleDocClick = async (id) => {
    try { const d = await api.getDocument(id); setDocDetail(d) } catch (e) {}
  }
  const handleRenew = async (id) => { await api.renewDocument(id); load() }
  const runSkill = async (name) => {
    setLoading(true); setAnswer(''); setThinkingSteps([])
    try { const r = await api.executeSkill(name); setAnswer(`${name}\n${JSON.stringify(r.result || r, null, 2)}`) } catch (e) { setAnswer('失败: ' + e.message) }
    setLoading(false)
  }
  const ROLES = { '新人': '新人', '核心成员': '成员', '主理人': '主理人' }

  if (isMobile) return <MobileView {...{ docs, stats, expiring, question, answer, role, loading, agentMode, skills, showUpload, uploadTitle, chatRef, uploadRef, setQuestion, setRole, setAgentMode, setShowUpload, setUploadTitle, handleRenew, handleUpload, ask, runSkill, load, ROLES }} />

  return (
    <div>
      <div className="h1" style={{ marginBottom: 18 }}>知识库</div>
      {showUpload && (
        <div className="card" style={{ padding: 20, marginBottom: 18 }}>
          <div className="h2" style={{ marginBottom: 12 }}>新建文档</div>
          <input placeholder="标题" value={uploadTitle} onChange={e => setUploadTitle(e.target.value)} className="input" style={{ marginBottom: 8 }} />
          <div ref={uploadRef} contentEditable suppressContentEditableWarning className="input" style={{ minHeight: 56, marginBottom: 12 }} />
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button onClick={() => setShowUpload(false)} className="btn-secondary">取消</button>
            <button onClick={handleUpload} className="btn">入库</button>
          </div>
        </div>
      )}

      {/* Main layout: left sidebar (docs) + right bento grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 14, height: 'calc(100vh - 140px)' }}>
        {/* Left: Document list — independent scroll */}
        <div className="card enter" style={{ padding: '14px 16px', overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
          <div className="h2" style={{ flexShrink: 0, marginBottom: 10, position: 'sticky', top: 0, background: '#fff', zIndex: 1, paddingBottom: 8 }}>文档 · {docs.length}</div>
          {expiring.length > 0 && (
            <div style={{ flexShrink: 0, padding: 8, background: '#FFFBEB', borderRadius: 6, marginBottom: 10, fontSize: 11 }}>
              <span style={{ color: '#D97706', fontWeight: 600 }}>{expiring.length} 份待保鲜</span>
              {expiring.slice(0, 2).map(d => (
                <button key={d.id} onClick={() => handleRenew(d.id)} className="btn-chip" style={{ display: 'block', marginTop: 4, width: '100%', textAlign: 'left', fontSize: 10 }}>{d.title.slice(0, 30)} → 续期</button>
              ))}
            </div>
          )}
          <div style={{ flex: 1, overflow: 'auto' }}>
            {docs.map(d => (
              <div key={d.id} onClick={() => handleDocClick(d.id)} style={{ padding: '7px 0', borderBottom: '1px solid var(--border-subtle)', fontSize: 12, cursor: 'pointer' }}>
                <div style={{ fontWeight: 500 }}>{d.title}</div>
                <div className="caption" style={{ marginTop: 2 }}>{d.file_type} · {d.chunk_count}块 {d.freshness === 'outdated' && '· 过期'}</div>
              </div>
            ))}
          </div>
          <div style={{ flexShrink: 0, paddingTop: 12, borderTop: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <button onClick={() => setShowUpload(true)} className="btn-secondary" style={{ width: '100%', fontSize: 12 }}>+ 新建文档</button>
            <button onClick={load} className="btn-secondary" style={{ width: '100%', fontSize: 12 }}>刷新</button>
          </div>
        </div>

        {/* Right: Bento grid (fixed-height cards only) */}
        <div className="bento" style={{ gridAutoRows: 'auto' }}>
          {/* Stats */}
          <div className="bento-1x1 card enter" style={{ ...cs, gridRow: 'span 1' }}>
            <div className="stat">{stats.document_count || 0}</div>
            <div className="caption" style={{ marginTop: 4 }}>文档</div>
          </div>
          <div className="bento-1x1 card enter" style={{ ...cs, gridRow: 'span 1' }}>
            <div className="stat" style={{ color: expiring.length ? '#D97706' : 'inherit' }}>{expiring.length || 0}</div>
            <div className="caption" style={{ marginTop: 4 }}>待保鲜</div>
          </div>

          {/* AI Chat — fills remaining space */}
          <div className="card enter" style={{ ...cs, display: 'flex', flexDirection: 'column', gridColumn: 'span 2', gridRow: 'span 3' }}>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 8, flexShrink: 0 }}>
              <span className="h2" style={{ flex: 1 }}>AI 对话</span>
              <button onClick={() => setAgentMode(!agentMode)} className="btn-chip" style={agentMode ? { background: 'var(--accent-subtle)', color: 'var(--accent)', borderColor: 'var(--accent)' } : {}}>Agent</button>
              {Object.entries(ROLES).map(([k, v]) => (
                <button key={k} onClick={() => setRole(k)} className="btn-chip" style={role === k ? { background: 'var(--accent-subtle)', color: 'var(--accent)', borderColor: 'var(--accent)' } : {}}>{v}</button>
              ))}
            </div>
            {thinkingSteps.length > 0 && (
              <div style={{ flexShrink: 0, marginBottom: 8 }}>
                {thinkingSteps.slice(0, 4).map((s, i) => (
                  <div key={i} style={{ fontSize: 11, color: 'var(--text-3)', padding: '3px 0', display: 'flex', gap: 6 }}><span>{s.type === 'tool_call' ? '→' : '·'}</span><span>{s.type === 'tool_call' ? s.tool : (s.content || '').slice(0, 60)}</span></div>
                ))}
              </div>
            )}
            <div ref={chatRef} className="no-scroll" style={{ flex: 1, overflow: 'auto', fontSize: 13, lineHeight: 1.8, color: 'var(--text)', whiteSpace: 'pre-wrap', paddingRight: 4 }}>
              {answer ? (
                <div style={{ borderLeft: '2px solid var(--accent)', paddingLeft: 14 }}>{answer}</div>
              ) : (
                <div style={{ textAlign: 'center', color: 'var(--text-3)', paddingTop: 40, fontSize: 13 }}>输入问题开始对话</div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexShrink: 0 }}>
              <input placeholder="输入问题..." value={question} onChange={e => setQuestion(e.target.value)} onKeyDown={e => e.key === 'Enter' && ask()} className="input" style={{ flex: 1 }} />
              <button onClick={ask} disabled={loading} className="btn">{loading ? '...' : '→'}</button>
            </div>
            {skills.length > 0 && (
              <div style={{ display: 'flex', gap: 6, marginTop: 8, flexShrink: 0, overflowX: 'auto', paddingBottom: 4 }} className="no-scroll">
                {skills.filter(s => !s.name.startsWith('lenny:')).slice(0, 6).map(s => (
                  <button key={s.name} onClick={() => runSkill(s.name)} className="btn-chip" style={{ whiteSpace: 'nowrap', flexShrink: 0 }}>{s.display_name || s.name}</button>
                ))}
              </div>
            )}
          </div>

          {/* Quick actions card */}
          <div className="bento-1x1 card enter" style={{ ...cs, gridRow: 'span 1' }}>
            <div className="caption" style={{ fontWeight: 600, marginBottom: 4 }}>接入</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', lineHeight: 1.6 }}>
              上传文档 → 分块 → 向量化 → 可检索
            </div>
          </div>
          <div className="bento-1x1 card enter" style={{ ...cs, gridRow: 'span 1' }}>
            <div style={{ fontSize: 28, fontWeight: 700 }}>{stats.chunk_count || 0}</div>
            <div className="caption" style={{ marginTop: 4 }}>向量块</div>
          </div>
        </div>
      </div>

      {docDetail && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1000, display: 'flex', justifyContent: 'center', alignItems: 'center', background: 'rgba(15,23,42,.4)' }} onClick={() => setDocDetail(null)}>
          <div className="card" style={{ width: 500, maxHeight: '80vh', padding: 24, overflow: 'auto' }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14 }}>
              <span className="h2">{docDetail.title}</span>
              <button onClick={() => setDocDetail(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'var(--text-3)' }}>×</button>
            </div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
              <span className="tag tag-accent">{docDetail.file_type}</span>
              <span className="tag">{docDetail.status}</span>
              <span className="tag">{docDetail.chunk_count} 块</span>
              <span className="caption" style={{ alignSelf: 'center' }}>大小: {docDetail.file_size} B</span>
            </div>
            {docDetail.freshness && docDetail.freshness !== 'valid' && (
              <div style={{ padding: 8, background: '#FFFBEB', borderRadius: 6, marginBottom: 12, fontSize: 12, color: '#D97706' }}>⚠️ 状态: {docDetail.freshness}</div>
            )}
            <div style={{ fontSize: 13, lineHeight: 1.8, color: 'var(--text)', whiteSpace: 'pre-wrap' }}>
              {docDetail.error_message ? <span style={{ color: '#DC2626' }}>错误: {docDetail.error_message}</span> : docDetail.content || <span style={{ color: 'var(--text-3)' }}>暂无内容</span>}
            </div>
            {docDetail.chunks && docDetail.chunks.length > 0 && (
              <div style={{ marginTop: 12, borderTop: '1px solid var(--border-subtle)', paddingTop: 12 }}>
                <div className="caption" style={{ fontWeight: 600, marginBottom: 8 }}>分块 ({docDetail.chunks.length})</div>
                {docDetail.chunks.map((c, i) => (
                  <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid var(--border-subtle)', fontSize: 12 }}>
                    <div className="caption" style={{ marginBottom: 4 }}>块 {c.index} · {c.tokens} tokens</div>
                    <div style={{ color: 'var(--text)', whiteSpace: 'pre-wrap' }}>{c.content}</div>
                  </div>
                ))}
              </div>
            )}
            <div className="caption" style={{ marginTop: 12 }}>
              创建: {new Date(docDetail.created_at).toLocaleString('zh-CN')}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function MobileView({ docs, stats, expiring, question, answer, role, loading, agentMode, skills, chatRef, setQuestion, setRole, setAgentMode, ask, load, ROLES, showUpload, setShowUpload, uploadTitle, setUploadTitle, uploadRef, handleUpload, handleRenew }) {
  return (
    <div style={{ paddingBottom: 80 }}>
      {/* AI Chat — primary interaction */}
      <div className="card" style={{ margin: '0 16px 12px', padding: 16 }}>
        <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
          <button onClick={() => setAgentMode(!agentMode)} style={{
            padding: '6px 14px', borderRadius: 20, border: agentMode ? '2px solid var(--accent)' : '1px solid var(--border)',
            background: agentMode ? 'var(--accent-subtle)' : '#fff', color: agentMode ? 'var(--accent)' : 'var(--text-2)',
            fontFamily: 'var(--font)', fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}>🧠 Agent</button>
          {Object.entries(ROLES).map(([k, v]) => (
            <button key={k} onClick={() => setRole(k)} style={{
              padding: '6px 14px', borderRadius: 20, border: role === k ? '2px solid var(--accent)' : '1px solid var(--border)',
              background: role === k ? 'var(--accent-subtle)' : '#fff', color: role === k ? 'var(--accent)' : 'var(--text-2)',
              fontFamily: 'var(--font)', fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}>{v}</button>
          ))}
        </div>
        <div ref={chatRef} style={{ maxHeight: 200, overflow: 'auto', fontSize: 15, lineHeight: 1.7, whiteSpace: 'pre-wrap', marginBottom: 10 }}>
          {answer || <div style={{ color: 'var(--text-3)', textAlign: 'center', padding: 20, fontSize: 14 }}>💡 输入问题，AI 从知识库中查找答案</div>}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input placeholder="输入问题..." value={question} onChange={e => setQuestion(e.target.value)} className="input" style={{ flex: 1, fontSize: 15 }} />
          <button onClick={ask} disabled={loading} className="btn" style={{ minWidth: 48, height: 44 }}>{loading ? '...' : '→'}</button>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 8, padding: '0 16px', marginBottom: 12 }}>
        <div className="card" style={{ flex: 1, padding: 12, textAlign: 'center' }}>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{stats.document_count || 0}</div>
          <div className="caption">文档</div>
        </div>
        <div className="card" style={{ flex: 1, padding: 12, textAlign: 'center' }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: expiring.length ? '#D97706' : 'inherit' }}>{expiring.length || 0}</div>
          <div className="caption">待保鲜</div>
        </div>
        <div className="card" style={{ flex: 1, padding: 12, textAlign: 'center' }}>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{stats.chunk_count || 0}</div>
          <div className="caption">向量块</div>
        </div>
      </div>

      {/* Documents */}
      <div style={{ padding: '0 16px' }}>
        {expiring.length > 0 && (
          <div className="card" style={{ padding: 12, marginBottom: 10, background: '#FFFBEB' }}>
            <span style={{ color: '#D97706', fontWeight: 600, fontSize: 13 }}>⚠️ {expiring.length} 份文档待保鲜</span>
            {expiring.slice(0, 2).map(d => (
              <button key={d.id} onClick={() => handleRenew(d.id)} className="btn-chip" style={{ display: 'block', marginTop: 4, width: '100%', textAlign: 'left' }}>{d.title.slice(0, 30)} → 续期</button>
            ))}
          </div>
        )}
        {docs.map(d => (
          <div key={d.id} className="card" style={{ padding: 14, marginBottom: 8 }}>
            <div style={{ fontWeight: 600, fontSize: 15 }}>{d.title}</div>
            <div className="caption" style={{ marginTop: 4 }}>{d.file_type} · {d.chunk_count}块 · {d.status} {d.freshness === 'outdated' && '· ⚠️过期'}</div>
          </div>
        ))}
        {docs.length === 0 && <div className="card" style={{ padding: 30, textAlign: 'center', color: 'var(--text-3)' }}>暂无文档</div>}
      </div>

      {/* Floating upload */}
      <button onClick={() => setShowUpload(!showUpload)} style={{
        position: 'fixed', bottom: 100, right: 20, width: 56, height: 56, borderRadius: 28,
        background: uploadTitle ? 'var(--accent)' : '#fff', color: uploadTitle ? '#fff' : 'var(--accent)',
        border: uploadTitle ? 'none' : '2px solid var(--accent)', fontSize: 24,
        boxShadow: '0 4px 20px rgba(15,118,110,.4)', cursor: 'pointer', zIndex: 300,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>{showUpload ? '×' : '+'}</button>

      {showUpload && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 500, background: 'rgba(0,0,0,.5)', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }} onClick={() => setShowUpload(false)}>
          <div onClick={e => e.stopPropagation()} style={{ background: '#fff', borderRadius: '16px 16px 0 0', padding: 16, maxHeight: '70vh' }}>
            <div className="h2" style={{ marginBottom: 10 }}>新建文档</div>
            <input placeholder="标题" value={uploadTitle} onChange={e => setUploadTitle(e.target.value)} className="input" style={{ marginBottom: 8, fontSize: 15 }} />
            <div ref={uploadRef} contentEditable suppressContentEditableWarning className="input" style={{ minHeight: 80, marginBottom: 12, fontSize: 15 }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => setShowUpload(false)} className="btn-secondary">取消</button>
              <button onClick={handleUpload} className="btn">入库</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
const cs = { padding: '16px 20px', overflow: 'hidden' }
