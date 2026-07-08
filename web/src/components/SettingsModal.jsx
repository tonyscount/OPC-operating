import { useState, useEffect } from 'react'
import { api } from '../api/client'

const PROVIDERS = [
  { key: 'deepseek', label: 'DeepSeek', url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  { key: 'openai', label: 'OpenAI', url: 'https://api.openai.com/v1', model: 'gpt-4o' },
  { key: 'qwen', label: '通义千问', url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
]

export default function SettingsModal({ onClose }) {
  const [provider, setProvider] = useState('deepseek')
  const [key, setKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [msg, setMsg] = useState('')
  const [config, setConfig] = useState(null)

  const current = PROVIDERS.find(p => p.key === provider)

  useEffect(() => {
    api.getLLMSettings().then(d => { setConfig(d); setProvider(d.provider || 'deepseek') }).catch(() => {})
  }, [])

  const save = async () => {
    if (!key.trim()) return; setSaving(true); setMsg('')
    try {
      const d = await api.updateLLMSettings({
        api_key: key.trim(), provider: current.key, base_url: current.url, model: current.model,
      })
      setSaved(true); setMsg('已应用'); setKey(''); setConfig(d)
      setTimeout(() => { setSaved(false); onClose() }, 1500)
    } catch (e) { setMsg('保存失败') }
    setSaving(false)
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1000, display: 'flex', justifyContent: 'center', alignItems: 'center', background: 'rgba(15,23,42,.4)', backdropFilter: 'blur(2px)' }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{
        width: 400, padding: 28, background: '#fff', borderRadius: 12, border: '1px solid var(--border)',
        boxShadow: '0 20px 60px rgba(0,0,0,.12)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <span style={{ fontWeight: 700, fontSize: 16, color: 'var(--text)' }}>API 设置</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'var(--text-3)' }}>×</button>
        </div>

        {/* Provider selector */}
        <div style={{ marginBottom: 16 }}>
          <div className="caption" style={{ marginBottom: 8, fontWeight: 600 }}>提供商</div>
          <div style={{ display: 'flex', gap: 6 }}>
            {PROVIDERS.map(p => (
              <button key={p.key} onClick={() => setProvider(p.key)} style={{
                flex: 1, padding: '8px 12px', borderRadius: 8, cursor: 'pointer', border: provider === p.key ? '2px solid var(--accent)' : '1px solid var(--border)',
                background: provider === p.key ? 'var(--accent-subtle)' : '#fff',
                color: provider === p.key ? 'var(--accent)' : 'var(--text-2)', fontSize: 12, fontWeight: 600,
                fontFamily: 'var(--font)', transition: 'all .15s',
              }}>{p.label}</button>
            ))}
          </div>
        </div>

        {/* Auto-filled info */}
        <div style={{ padding: 10, background: 'var(--bg)', borderRadius: 8, marginBottom: 16, fontSize: 12, color: 'var(--text-3)', lineHeight: 1.8 }}>
          <div>接口: {current?.url}</div>
          <div>模型: {current?.model}</div>
          {config?.key_preview && <div>当前 Key: <span style={{ color: config.is_configured ? 'var(--accent)' : '#DC2626' }}>{config.key_preview}</span></div>}
        </div>

        {/* Key input */}
        <div className="caption" style={{ fontWeight: 600, marginBottom: 6 }}>API Key</div>
        <input placeholder="sk-..." value={key} onChange={e => setKey(e.target.value)} onKeyDown={e => e.key === 'Enter' && save()}
          className="input" autoFocus
          style={{ marginBottom: 14, fontFamily: 'ui-monospace, monospace', fontSize: 13 }} />

        {msg && <div style={{ marginBottom: 12, fontSize: 13, color: saved ? 'var(--accent)' : '#DC2626', fontWeight: 500 }}>{msg}</div>}

        <button onClick={save} disabled={saving || saved || !key.trim()} style={{
          width: '100%', height: 40, border: 'none', borderRadius: 8,
          background: saved ? 'var(--accent)' : 'var(--accent)',
          color: '#fff', fontSize: 14, fontWeight: 600, fontFamily: 'var(--font)',
          cursor: (saving || saved) ? 'default' : 'pointer',
          opacity: (saving || !key.trim()) ? .5 : 1,
          transition: 'all .2s',
        }}>
          {saved ? '✓ 已应用' : saving ? '保存中...' : '保存'}
        </button>
      </div>
    </div>
  )
}
