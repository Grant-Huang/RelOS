/**
 * Layout — 应用主布局（侧边栏 + 主内容区）
 */
import Sidebar from './Sidebar'

export default function Layout({ children }) {
  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  )
}
