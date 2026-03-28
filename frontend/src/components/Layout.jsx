/**
 * Layout — 应用主布局（侧边栏 + 主内容区）
 */
import Sidebar from './Sidebar'

export default function Layout({ children }) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg3)' }}>
      <Sidebar />
      <main style={{ flex: 1, overflowY: 'auto', background: 'var(--bg3)' }}>
        {children}
      </main>
    </div>
  )
}
