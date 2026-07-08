import { useState, useEffect } from 'react'
import { api } from '../api/client'

export default function TradePage() {
  const [tab, setTab] = useState('products') // products | orders | create
  const [products, setProducts] = useState([])
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)

  // Create form
  const [title, setTitle] = useState('')
  const [price, setPrice] = useState('')
  const [category, setCategory] = useState('service')
  const [desc, setDesc] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const [p, o] = await Promise.all([
        api.getProducts ? api.getProducts() : fetch('/api/v1/trade/products', { headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` } }).then(r => r.json()),
        api.getOrders ? api.getOrders() : fetch('/api/v1/trade/orders', { headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` } }).then(r => r.json()),
      ])
      setProducts(p.items || [])
      setOrders(Array.isArray(o) ? o : o.items || [])
    } catch (e) { /* ignore */ }
    setLoading(false)
  }

  // Register API methods if not in client.js
  useEffect(() => {
    if (!api.getProducts) {
      api.getProducts = () =>
        fetch('/api/v1/trade/products', { headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` } }).then(r => r.json())
      api.createProduct = (data) =>
        fetch('/api/v1/trade/products?' + new URLSearchParams(data), { method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` } })
      api.getOrders = () =>
        fetch('/api/v1/trade/orders', { headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` } }).then(r => r.json())
    }
  }, [])

  useEffect(() => { load() }, [])

  const createProduct = async () => {
    if (!title.trim() || !price) return
    const params = new URLSearchParams({ title: title.trim(), price, category, description: desc })
    await fetch('/api/v1/trade/products?' + params, { method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('opc_token')}` } })
    setTitle(''); setPrice(''); setDesc(''); setCategory('service')
    setTab('products'); load()
  }

  const categories = [
    { key: 'service', label: '服务' },
    { key: 'goods', label: '实物' },
    { key: 'digital', label: '数字产品' },
  ]

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h1 className="h1" style={{ marginBottom: 0, flex: 1 }}>交易市场</h1>
        <div style={{ display: 'flex', gap: 4 }}>
          {[
            { key: 'products', label: '商品' },
            { key: 'orders', label: '我的订单' },
            { key: 'create', label: '+ 发布' },
          ].map(t => (
            <button key={t.key} onClick={() => setTab(t.key)} className="btn-chip"
              style={tab === t.key ? { background: 'var(--accent-subtle)', color: 'var(--accent)', borderColor: 'var(--accent)' } : {}}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-3)' }}>加载中...</div>}

      {/* Products Tab */}
      {!loading && tab === 'products' && (
        <div>
          {products.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-3)' }}>
              暂无商品 — 一人公司主理人可以在上架服务、数字产品或实物
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
              {products.map(p => (
                <div key={p.id} className="card" style={{ padding: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                    <span style={{ fontWeight: 600, fontSize: 15 }}>{p.title}</span>
                    <span className="tag" style={{ background: catColor(p.category) }}>{catLabel(p.category)}</span>
                  </div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent)', marginBottom: 4 }}>
                    ¥{Number(p.price).toFixed(2)}
                  </div>
                  <div className="caption" style={{ marginBottom: 8 }}>已售 {p.order_count || 0} 单</div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {p.stock === -1 ? (
                      <span className="tag" style={{ background: '#D1FAE5', color: '#065F46' }}>无限库存</span>
                    ) : (
                      <span className="tag">{p.stock > 0 ? `库存 ${p.stock}` : '已售罄'}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Orders Tab */}
      {!loading && tab === 'orders' && (
        <div>
          {orders.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-3)' }}>暂无订单</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {orders.map(o => (
                <div key={o.id} className="card" style={{ padding: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>订单 #{o.id?.slice(0, 8)}</div>
                    <div className="caption">{new Date(o.created_at).toLocaleString('zh-CN')}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontWeight: 700, fontSize: 16 }}>¥{Number(o.total_amount).toFixed(2)}</div>
                    <span className="tag" style={{ background: statusColor(o.status) }}>{statusLabel(o.status)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Create Tab */}
      {tab === 'create' && (
        <div className="card" style={{ padding: 24, maxWidth: 500 }}>
          <h2 className="h2">发布商品/服务</h2>
          <div style={{ marginBottom: 12 }}>
            <div className="caption" style={{ marginBottom: 4, fontWeight: 600 }}>标题</div>
            <input value={title} onChange={e => setTitle(e.target.value)} className="input" placeholder="如：Linux 服务器运维咨询" />
          </div>
          <div style={{ marginBottom: 12 }}>
            <div className="caption" style={{ marginBottom: 4, fontWeight: 600 }}>分类</div>
            <div style={{ display: 'flex', gap: 6 }}>
              {categories.map(c => (
                <button key={c.key} onClick={() => setCategory(c.key)} className="btn-chip"
                  style={category === c.key ? { background: 'var(--accent-subtle)', color: 'var(--accent)', borderColor: 'var(--accent)' } : {}}>
                  {c.label}
                </button>
              ))}
            </div>
          </div>
          <div style={{ marginBottom: 12 }}>
            <div className="caption" style={{ marginBottom: 4, fontWeight: 600 }}>价格 (¥)</div>
            <input type="number" value={price} onChange={e => setPrice(e.target.value)} className="input" placeholder="0.00" min="0" step="0.01" />
          </div>
          <div style={{ marginBottom: 16 }}>
            <div className="caption" style={{ marginBottom: 4, fontWeight: 600 }}>描述</div>
            <textarea value={desc} onChange={e => setDesc(e.target.value)} className="input" rows={3} placeholder="描述你的服务内容..." />
          </div>
          <button onClick={createProduct} disabled={!title.trim() || !price} className="btn" style={{ width: '100%' }}>
            发布
          </button>
        </div>
      )}
    </div>
  )
}

function catColor(c) {
  const m = { service: '#DBEAFE', goods: '#FEF3C7', digital: '#EDE9FE' }
  return m[c] || '#F3F4F6'
}

function catLabel(c) {
  const m = { service: '服务', goods: '实物', digital: '数字' }
  return m[c] || c
}

function statusColor(s) {
  const m = { pending: '#FEF3C7', completed: '#D1FAE5', cancelled: '#FEE2E2', approved: '#D1FAE5' }
  return m[s] || '#F3F4F6'
}

function statusLabel(s) {
  const m = { pending: '待处理', completed: '已完成', cancelled: '已取消', approved: '已通过' }
  return m[s] || s
}
