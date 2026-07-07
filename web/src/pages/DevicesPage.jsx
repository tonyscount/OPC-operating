import { useState, useEffect } from 'react'
import { api } from '../api/client'

export default function DevicesPage() {
  const [devices, setDevices] = useState([]); const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ name: '', device_type: 'opc_gateway', ip_address: '', location: '' })

  const load = () => api.getDevices().then(d => setDevices(d.items || []))
  useEffect(() => { load() }, [])

  const addDevice = async (e) => {
    e.preventDefault()
    const fd = new FormData(); fd.append('name', form.name); fd.append('device_type', form.device_type); fd.append('ip_address', form.ip_address); fd.append('location', form.location)
    const opts = { method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` }, body: fd }
    await fetch('/api/v1/devices', opts); setShowAdd(false); setForm({ name: '', device_type: 'opc_gateway', ip_address: '', location: '' }); load()
  }

  const updateStatus = async (id, status) => {
    const fd = new FormData(); fd.append('status', status)
    const opts = { method: 'PATCH', headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` }, body: fd }
    await fetch(`/api/v1/devices/${id}/status`, opts); load()
  }

  const online = devices.filter(d => d.status === 'online').length

  return (
    <div>
      <div className="h1" style={{ marginBottom: 16 }}>设备管理</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
        {[{ label: '设备总数', value: devices.length }, { label: '在线', value: online }, { label: '离线', value: devices.length - online }, { label: '待注册', value: 0 }].map(s => (
          <div key={s.label} className="card" style={{ padding: 18 }}>
            <div className="stat">{s.value}</div>
            <div className="caption" style={{ marginTop: 4 }}>{s.label}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 14 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14, alignContent: 'start' }}>
          {devices.map(d => (
            <div key={d.id} className="card" style={{ padding: 18 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                <span style={{ fontWeight: 600, fontSize: 14 }}>{d.name}</span>
                <span className="tag" style={d.status === 'online' ? { background: 'var(--accent-subtle)', color: 'var(--accent)' } : { background: '#F1F5F9', color: 'var(--text-3)' }}>{d.status}</span>
              </div>
              {d.ip_address && <div className="caption">IP: {d.ip_address}</div>}
              {d.location && <div className="caption">位置: {d.location}</div>}
              <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
                {d.status !== 'online' && <button onClick={() => updateStatus(d.id, 'online')} className="btn-secondary" style={{ fontSize: 11 }}>上线</button>}
                {d.status !== 'offline' && <button onClick={() => updateStatus(d.id, 'offline')} className="btn-secondary" style={{ fontSize: 11 }}>离线</button>}
              </div>
            </div>
          ))}
          {devices.length === 0 && <div className="card" style={{ padding: 24, textAlign: 'center', color: 'var(--text-3)', fontSize: 13 }}>暂无设备</div>}
        </div>

        <div className="card" style={{ padding: 18, height: 'fit-content' }}>
          <div className="h2" style={{ marginBottom: 14 }}>{showAdd ? '注册设备' : '操作'}</div>
          {showAdd ? (
            <form onSubmit={addDevice}>
              <input placeholder="设备名称" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="input" style={{ marginBottom: 8 }} required />
              <select value={form.device_type} onChange={e => setForm({ ...form, device_type: e.target.value })} className="input" style={{ marginBottom: 8 }}>
                <option value="opc_gateway">OPC 网关</option><option value="plc">PLC</option><option value="sensor">传感器</option><option value="camera">摄像头</option><option value="other">其他</option>
              </select>
              <input placeholder="IP 地址" value={form.ip_address} onChange={e => setForm({ ...form, ip_address: e.target.value })} className="input" style={{ marginBottom: 8 }} />
              <input placeholder="位置" value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} className="input" style={{ marginBottom: 12 }} />
              <button type="submit" className="btn" style={{ width: '100%' }}>注册</button>
              <button type="button" onClick={() => setShowAdd(false)} className="btn-secondary" style={{ width: '100%', marginTop: 6 }}>取消</button>
            </form>
          ) : (
            <button onClick={() => setShowAdd(true)} className="btn" style={{ width: '100%' }}>+ 注册新设备</button>
          )}
        </div>
      </div>
    </div>
  )
}
