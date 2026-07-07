import { useState, useEffect, useRef } from 'react'

export default function SkillPage({ isMobile }) {
  const [skills, setSkills] = useState([]); const [selected, setSelected] = useState(null)
  const [params, setParams] = useState({}); const [result, setResult] = useState(null)
  const [error, setError] = useState(null); const [executing, setExecuting] = useState(false)
  const [search, setSearch] = useState(''); const [history, setHistory] = useState([])

  const token = () => localStorage.getItem('opc_token')
  useEffect(() => {
    fetch('/api/v1/skills', { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json()).then(d => setSkills((d.skills || []).filter(s => !s.name.startsWith('lenny:'))))
  }, [])

  const filtered = skills.filter(s => !search || s.name.toLowerCase().includes(search.toLowerCase()) || (s.display_name || '').toLowerCase().includes(search.toLowerCase()))
  const selectSkill = (s) => { setSelected(s); setResult(null); setError(null); const d = {}; if (s.parameters) Object.entries(s.parameters).forEach(([k, v]) => { d[k] = v.default !== undefined ? v.default : '' }); setParams(d) }

  const execute = async () => {
    if (!selected) return; setExecuting(true); setResult(null); setError(null)
    try {
      const r = await fetch('/api/v1/skills/execute', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token()}` }, body: JSON.stringify({ skill_name: selected.name, parameters: params }) }).then(r => r.json())
      if (r.success) { setResult(r.result); setHistory(prev => [{ skill: selected.name, time: new Date().toISOString(), ok: true }, ...prev].slice(0, 20)) }
      else { setError(r.error); setHistory(prev => [{ skill: selected.name, time: new Date().toISOString(), ok: false, err: r.error }, ...prev].slice(0, 20)) }
    } catch (e) { setError(e.message) }
    setExecuting(false)
  }

  if (isMobile) return <MobileSkillView {...{ skills, selected, selectSkill, params, setParams, execute, result, error, executing, search, setSearch, history, filtered }} />

  const col = '240px 1fr 260px'
  return (
    <div>
      <div className="h1" style={{ marginBottom: 16 }}>Skills</div>
      <div style={{ display: 'grid', gridTemplateColumns: col, gap: 14, height: isMobile ? 'auto' : 'calc(100vh - 120px)' }}>
        {/* List */}
        <div className="card" style={{ padding: 16, overflow: 'auto' }}>
          <div className="h2" style={{ marginBottom: 10 }}>Skills</div>
          <input placeholder="搜索..." value={search} onChange={e => setSearch(e.target.value)} className="input" style={{ marginBottom: 10 }} />
          {filtered.map(s => {
            const active = selected?.name === s.name
            return (
              <button key={s.name} onClick={() => selectSkill(s)} className="card" style={{
                width: '100%', padding: 10, marginBottom: 4, textAlign: 'left', cursor: 'pointer', border: 'none',
                background: active ? 'var(--accent-subtle)' : '#fff',
                borderLeft: active ? '3px solid var(--accent)' : '3px solid transparent',
              }}>
                <div style={{ fontWeight: 600, fontSize: 12, color: active ? 'var(--accent)' : 'var(--text)' }}>{s.display_name || s.name}</div>
                <div className="caption" style={{ marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.description?.slice(0, 50)}</div>
              </button>
            )
          })}
        </div>

        {/* Execute */}
        <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
          {!selected ? (
            <div style={{ textAlign: 'center', color: 'var(--text-3)', paddingTop: 40, fontSize: 13 }}>选择左侧 Skill 开始</div>
          ) : (
            <>
              <div className="h2">{selected.display_name || selected.name}</div>
              <div className="caption" style={{ marginBottom: 14 }}>{selected.description}</div>
              {selected.parameters && Object.keys(selected.parameters).length > 0 && (
                <div style={{ marginBottom: 14 }}>
                  <div className="caption" style={{ marginBottom: 6, fontWeight: 600 }}>参数</div>
                  {Object.entries(selected.parameters).map(([k, v]) => (
                    <div key={k} style={{ marginBottom: 8 }}>
                      <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 3 }}>{k} ({v.type || 'string'}{v.required ? ', 必填' : ''})</div>
                      {v.type === 'boolean' ? (
                        <select value={params[k]?.toString() || 'false'} onChange={e => setParams({ ...params, [k]: e.target.value === 'true' })} className="input">
                          <option value="true">true</option><option value="false">false</option>
                        </select>
                      ) : v.type === 'integer' || v.type === 'number' ? (
                        <input type="number" value={params[k] || ''} onChange={e => setParams({ ...params, [k]: e.target.value })} placeholder={v.description || k} className="input" />
                      ) : (
                        <input value={params[k] || ''} onChange={e => setParams({ ...params, [k]: e.target.value })} placeholder={v.description || k} className="input" />
                      )}
                    </div>
                  ))}
                </div>
              )}
              <button onClick={execute} disabled={executing} className="btn" style={{ width: '100%', marginBottom: 14 }}>{executing ? '执行中...' : '执行'}</button>
              {error && <div style={{ padding: 12, background: '#FEF2F2', borderRadius: 6, marginBottom: 12 }}><div style={{ color: '#DC2626', fontSize: 12, fontWeight: 600 }}>错误</div><pre style={{ color: '#DC2626', fontSize: 11, margin: '4px 0 0', whiteSpace: 'pre-wrap' }}>{error}</pre></div>}
              {result && (
                <div style={{ padding: 12, background: 'var(--accent-subtle)', borderRadius: 6, flex: 1, overflow: 'auto' }}>
                  <div style={{ color: 'var(--accent)', fontSize: 12, fontWeight: 600, marginBottom: 6 }}>结果</div>
                  <pre style={{ fontSize: 12, margin: 0, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{JSON.stringify(result, null, 2)}</pre>
                </div>
              )}
            </>
          )}
        </div>

        {/* Detail + History */}
        <div className="card" style={{ padding: 16, overflow: 'auto' }}>
          {selected ? (
            <>
              <div className="h2" style={{ marginBottom: 10 }}>详情</div>
              <div style={{ fontSize: 12, lineHeight: 1.8 }}>
                <div style={{ marginBottom: 8 }}><span className="caption">名称</span><br />{selected.name}</div>
                <div style={{ marginBottom: 8 }}><span className="caption">描述</span><br />{selected.description?.slice(0, 200)}</div>
                {selected.parameters && Object.keys(selected.parameters).length > 0 && (
                  <div>
                    <span className="caption">参数</span>
                    {Object.entries(selected.parameters).map(([k, v]) => (
                      <div key={k} style={{ background: 'var(--bg)', padding: '4px 8px', borderRadius: 6, marginTop: 4, fontSize: 11 }}>
                        <span style={{ fontWeight: 600 }}>{k}</span>: {v.type || 'string'}{v.required ? ' (必填)' : ''}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : <div style={{ textAlign: 'center', color: 'var(--text-3)', paddingTop: 20, fontSize: 13 }}>选择 Skill</div>}
          {history.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div className="caption" style={{ fontWeight: 600, marginBottom: 6 }}>执行历史</div>
              {history.slice(0, 10).map((h, i) => (
                <div key={i} style={{ padding: '4px 0', borderBottom: '1px solid var(--border-subtle)', fontSize: 11 }}>
                  <span style={{ color: h.ok ? 'var(--accent)' : '#DC2626' }}>{h.ok ? '✓' : '✗'}</span>
                  <span style={{ marginLeft: 6, color: 'var(--text-2)' }}>{h.skill}</span>
                  <span style={{ marginLeft: 8, color: 'var(--text-3)' }}>{new Date(h.time).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function MobileSkillView({ skills, selected, selectSkill, params, setParams, execute, result, error, executing, search, setSearch, history, filtered }) {
  return (
    <div style={{ padding: '0 16px 80px' }}>
      <input placeholder="搜索 Skill..." value={search} onChange={e => setSearch(e.target.value)} className="input" style={{ marginBottom: 10, fontSize: 15 }} />
      <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 10, marginBottom: 10 }}>
        {filtered.map(s => (
          <button key={s.name} onClick={() => selectSkill(s)} style={{
            padding: '8px 16px', borderRadius: 20, whiteSpace: 'nowrap', flexShrink: 0,
            border: selected?.name === s.name ? '2px solid var(--accent)' : '1px solid var(--border)',
            background: selected?.name === s.name ? 'var(--accent-subtle)' : '#fff',
            color: selected?.name === s.name ? 'var(--accent)' : 'var(--text-2)',
            fontFamily: 'var(--font)', fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}>{s.display_name || s.name}</button>
        ))}
      </div>
      {selected && (
        <div className="card" style={{ padding: 16, marginBottom: 10 }}>
          <div className="h2">{selected.display_name || selected.name}</div>
          <div className="caption" style={{ marginBottom: 12, marginTop: 4 }}>{selected.description}</div>
          {selected.parameters && Object.keys(selected.parameters).length > 0 && Object.entries(selected.parameters).map(([k, v]) => (
            <div key={k} style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 4 }}>{k} ({v.type || 'string'}{v.required ? ', 必填' : ''})</div>
              <input value={params[k] || ''} onChange={e => setParams({ ...params, [k]: e.target.value })} className="input" style={{ fontSize: 15 }} />
            </div>
          ))}
          <button onClick={execute} disabled={executing} className="btn" style={{ width: '100%', marginBottom: 10 }}>{executing ? '执行中...' : '执行'}</button>
          {error && <div style={{ padding: 10, background: '#FEF2F2', borderRadius: 8, marginBottom: 10, color: '#DC2626', fontSize: 13 }}>❌ {error}</div>}
          {result && <div style={{ padding: 10, background: 'var(--accent-subtle)', borderRadius: 8, fontSize: 13 }}><pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(result, null, 2)}</pre></div>}
        </div>
      )}
      {history.length > 0 && (
        <div className="card" style={{ padding: 14 }}>
          <div className="caption" style={{ fontWeight: 600, marginBottom: 6 }}>执行历史</div>
          {history.slice(0, 10).map((h, i) => (
            <div key={i} style={{ padding: '4px 0', borderBottom: '1px solid var(--border-subtle)', fontSize: 12 }}>
              <span style={{ color: h.ok ? 'var(--accent)' : '#DC2626' }}>{h.ok ? '✓' : '✗'}</span>
              <span style={{ margin: '0 8px', color: 'var(--text-2)' }}>{h.skill}</span>
              <span style={{ color: 'var(--text-3)' }}>{new Date(h.time).toLocaleTimeString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
