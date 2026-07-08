import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          minHeight: 300, padding: 40, textAlign: 'center',
        }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⚠</div>
          <h2 style={{ marginBottom: 8, color: 'var(--text)' }}>页面出错了</h2>
          <p style={{ color: 'var(--text-3)', fontSize: 13, marginBottom: 20, maxWidth: 400 }}>
            {this.state.error?.message || '发生了意外错误'}
          </p>
          <button onClick={() => { this.setState({ hasError: false }); window.location.reload() }} className="btn">
            刷新页面
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
