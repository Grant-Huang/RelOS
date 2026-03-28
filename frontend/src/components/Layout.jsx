/**
 * Layout — 工作台侧栏 + 主题切换 + 移动端抽屉
 */
import { useState } from 'react'
import { Menu, X } from 'lucide-react'
import WorkbenchSidebar from './WorkbenchSidebar'
import ThemeToggle from './ThemeToggle'

export default function Layout({ children }) {
  const [open, setOpen] = useState(false)

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg3)' }}>
      <Sidebar />
      <main style={{ flex: 1, overflowY: 'auto', background: 'var(--bg3)' }}>
        {children}
      </main>
    </div>
  )
}
