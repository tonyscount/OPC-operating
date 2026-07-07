import { useState, useEffect } from 'react'
import { api } from '../api/client'

export default function OpsPage() {
  const [dash, setDash] = useState(null)
  const [taskStatus, setTaskStatus] = useState(null)
  const [dailyResult, setDailyResult] = useState(null)
  const [running, setRunning] = useState(false)
  const tok = () => localStorage.getItem('opc_token')

  const load = () => {
    api.getDashboard().then(setDash)
    fetch('/api/v1/schedule/status', { headers: { Authorization: `Bearer ${tok()}` } }).then(r => r.json()).then(setTaskStatus)
  }
  useEffect(() => { load() }, [])

  const runDaily = async () => {
    setRunning(true); setDailyResult(null)
    try {
      const r = await fetch('/api/v1/schedule/run-daily', { method: 'POST', headers: { Authorization: `Bearer ${tok()}` } })
      setDailyResult(await r.json())
    } catch (e) { setDailyResult({ error: e.message }) }
    setRunning(false)
    setTimeout(() => load(), 1000)
  }

  const cards = [
    { key: 'users', label: '用户', color: '#0F766E' },
    { key: 'posts', label: '动态', color: '#0F766E' },
    { key: 'documents', label: '文档', color: '#0F766E' },
    { key: 'orders', label: '订单', color: '#0F766E' },
  ]

  return (
    <div>
      <div className="h1" style={{ marginBottom: 18 }}>运营仪表盘</div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
        {cards.map(c => (
          <div key={c.key} className="card" style={{ padding: 18 }}>
            <div className="stat">{dash?.[c.key] ?? '—'}</div>
            <div className="caption" style={{ marginTop: 4 }}>{c.label}</div>
          </div>
        ))}
      </div>

      {/* Manual trigger */}
      <div className="card" style={{ padding: 16, marginBottom: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div className="h2">每日任务</div>
            <div className="caption" style={{ marginTop: 2 }}>保鲜检查 + 运营简报生成 (无需 Redis)</div>
          </div>
          <button onClick={runDaily} disabled={running} className="btn" style={{ fontSize: 13 }}>
            {running ? '运行中...' : '▶ 立即执行'}
          </button>
        </div>
        {dailyResult && (
          <div style={{ marginTop: 12, padding: 12, background: dailyResult.error ? '#FEF2F2' : 'var(--accent-subtle)', borderRadius: 8, fontSize: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 6, color: dailyResult.error ? '#DC2626' : 'var(--accent)' }}>
              {dailyResult.error ? '执行失败' : `完成 · ${dailyResult.elapsed_ms}ms`}
            </div>
            {dailyResult.results && Object.entries(dailyResult.results).map(([k, v]) => (
              <div key={k} style={{ marginTop: 8 }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>{k === 'freshness' ? '🧹 保鲜检查' : '📊 运营简报'}</div>
                {k === 'briefing' && v.results ? (
                  v.results.map((r, i) => (
                    <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                      <div style={{ fontWeight: 600, fontSize: 12 }}>{r.tenant}</div>
                      {r.briefing ? (
                        <div style={{ whiteSpace: 'pre-wrap', fontSize: 12, color: 'var(--text)', marginTop: 4, lineHeight: 1.6 }}>{r.briefing}</div>
                      ) : (
                        <div className="caption">snapshot: {JSON.stringify(r.snapshot)}</div>
                      )}
                      {r.error && <div style={{ color: '#DC2626', fontSize: 11 }}>{r.error}</div>}
                    </div>
                  ))
                ) : (
                  <span className="caption">{JSON.stringify(v)}</span>
                )}
              </div>
            ))}
            {dailyResult.error && <div style={{ color: '#DC2626' }}>{dailyResult.error}</div>}
          </div>
        )}
      </div>

      {taskStatus && (
        <div style={{ marginBottom: 20 }}>
          <div className="h2" style={{ marginBottom: 10 }}>自动化运营</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 14 }}>
            {[
              { label: '定时任务', ok: taskStatus.health?.scheduled_healthy, total: taskStatus.health?.scheduled_total },
              { label: '事件驱动', ok: taskStatus.health?.event_driven_healthy, total: taskStatus.health?.event_driven_total },
              { label: '30天成功率', value: taskStatus.health?.success_rate_30d + '%' },
            ].map(h => (
              <div key={h.label} className="card" style={{ padding: 18 }}>
                <div className="caption" style={{ marginBottom: 4 }}>{h.label}</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent)' }}>{h.value || `${h.ok}/${h.total}`}</div>
              </div>
            ))}
          </div>
          <div className="card" style={{ padding: 16 }}>
            <div className="caption" style={{ fontWeight: 600, marginBottom: 8 }}>最近执行</div>
            {(taskStatus.recent_executions || []).slice(0, 10).map((e, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '80px 1fr 70px 60px', gap: 12, padding: '5px 0', borderBottom: '1px solid var(--border-subtle)', fontSize: 12, alignItems: 'center' }}>
                <span style={{ color: 'var(--text-3)' }}>{e.time ? new Date(e.time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '—'}</span>
                <span>{e.task_name}</span>
                <span style={{ color: 'var(--text-3)', fontSize: 11 }}>{e.trigger === 'scheduled' ? '定时' : '事件'}</span>
                <span style={{ color: e.status === 'success' ? 'var(--accent)' : '#DC2626', fontWeight: 600, textAlign: 'right' }}>{e.status === 'success' ? 'OK' : 'FAIL'}</span>
              </div>
            ))}
            {(!taskStatus.recent_executions || taskStatus.recent_executions.length === 0) && (
              <div style={{ textAlign: 'center', color: 'var(--text-3)', padding: 16, fontSize: 12 }}>暂无执行记录</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
