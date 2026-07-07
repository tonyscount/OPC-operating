import { useState, useEffect } from 'react'

/**
 * Minimal SVG sparkline — Phenomenon Studio style
 * No heavy charting library, just clean data visualization
 */

function Sparkline({ data, height = 120, color = '#0F766E', label = '' }) {
  if (!data || data.length < 2) return <div className="card" style={{ padding: 24, textAlign: 'center', color: 'var(--text-3)' }}>数据不足</div>
  const padding = 8; const w = '100%'; const max = Math.max(...data, 1); const min = Math.min(...data, 0)
  const range = max - min || 1
  const h = height - padding * 2
  const step = 100 / (data.length - 1)
  const points = data.map((v, i) => `${i * step},${padding + h - ((v - min) / range) * h}`).join(' ')

  return (
    <div className="card" style={{ padding: '16px 20px' }}>
      <div className="caption" style={{ fontWeight: 600, marginBottom: 8 }}>{label}</div>
      <svg viewBox={`0 0 100 ${height}`} style={{ width: '100%', height }}>
        {/* Grid lines */}
        {[0, .25, .5, .75, 1].map(r => (
          <line key={r} x1="0" y1={padding + h * (1 - r)} x2="100" y2={padding + h * (1 - r)} stroke="var(--border-subtle)" strokeWidth=".5" />
        ))}
        {/* Area fill */}
        <polygon points={`0,${padding + h} ${points} 100,${padding + h}`} fill={color} opacity=".08" />
        {/* Line */}
        <polyline points={points} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        {/* Dots */}
        {data.map((v, i) => (
          <circle key={i} cx={i * step} cy={padding + h - ((v - min) / range) * h} r="1.5" fill={color} />
        ))}
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        <span className="caption">{max}</span>
        <span className="caption">{min}</span>
      </div>
    </div>
  )
}

function BarChart({ data, label = '', color = '#0F766E' }) {
  if (!data || data.length === 0) return null
  const max = Math.max(...data.map(d => d.value), 1)
  return (
    <div className="card" style={{ padding: '16px 20px' }}>
      <div className="caption" style={{ fontWeight: 600, marginBottom: 12 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 100 }}>
        {data.map((d, i) => (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <span className="caption" style={{ fontSize: 9 }}>{d.value || 0}</span>
            <div style={{
              width: '100%', height: `${(d.value / max) * 80}px`, minHeight: d.value > 0 ? 4 : 0,
              background: color, borderRadius: '3px 3px 0 0', opacity: .8,
              transition: 'height .4s ease',
            }} />
            <span className="caption" style={{ fontSize: 9 }}>{d.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function DataPage() {
  const [trend, setTrend] = useState(null)
  const [overview, setOverview] = useState(null)
  const [range, setRange] = useState('7d')

  const token = () => localStorage.getItem('opc_token')
  const hdr = () => ({ Authorization: `Bearer ${token()}`, 'Content-Type': 'application/json' })

  useEffect(() => {
    fetch('/api/v1/skills/execute', { method: 'POST', headers: hdr(),
      body: JSON.stringify({ skill_name: 'data_query', parameters: { metric: 'trend', time_range: range } })
    }).then(r => r.json()).then(d => setTrend(d.result?.data || []))

    fetch('/api/v1/skills/execute', { method: 'POST', headers: hdr(),
      body: JSON.stringify({ skill_name: 'data_query', parameters: { metric: 'overview', time_range: range } })
    }).then(r => r.json()).then(d => setOverview(d.result))
  }, [range])

  const postData = (trend || []).map(d => d.posts)
  const userData = (trend || []).map(d => d.new_users)
  const barData = (trend || []).map(d => ({ label: d.day, value: d.posts + d.new_users }))
  const totalPosts = postData.reduce((a, b) => a + b, 0)
  const totalUsers = userData.reduce((a, b) => a + b, 0)

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
        <span className="h1" style={{ marginBottom: 0 }}>数据</span>
        <div style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
          {['7d', '30d'].map(r => (
            <button key={r} onClick={() => setRange(r)} className="btn-chip"
              style={range === r ? { background: 'var(--accent-subtle)', color: 'var(--accent)', borderColor: 'var(--accent)' } : {}}>
              {r === '7d' ? '近 7 天' : '近 30 天'}
            </button>
          ))}
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
        {[
          { label: '总帖数', value: totalPosts, change: overview?.posts ? `共 ${overview.posts}` : '' },
          { label: '新成员', value: totalUsers, change: overview?.members ? `共 ${overview.members}` : '' },
          { label: '互动率', value: overview?.engagement_value || overview?.engagement || 0, unit: '%', change: '' },
          { label: '文档', value: overview?.documents || 0, change: overview?.orders != null ? `${overview.orders} 订单` : '' },
        ].map(s => (
          <div key={s.label} className="card" style={{ padding: '16px 20px' }}>
            <div className="caption">{s.label}</div>
            <div style={{ fontSize: 28, fontWeight: 700, marginTop: 4 }}>{s.value}{s.unit || ''}</div>
            {s.change && <div className="caption" style={{ marginTop: 4, color: 'var(--accent)' }}>{s.change}</div>}
          </div>
        ))}
      </div>

      {/* Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <Sparkline data={postData} height={140} label="每日发帖趋势" />
        <Sparkline data={userData} height={140} label="每日新增成员" color="#D97706" />
      </div>

      <div style={{ marginTop: 14 }}>
        <BarChart data={barData} label="每日活跃度 (帖子 + 新成员)" />
      </div>

      {(!trend || trend.length === 0) && (
        <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--text-3)' }}>
          数据积累中，发布几条动态后这里会显示趋势图
        </div>
      )}
    </div>
  )
}
