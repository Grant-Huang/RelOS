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
    <div className="flex h-screen overflow-hidden wb-main">
      <WorkbenchSidebar className="hidden md:flex" />

      <div className="md:hidden fixed top-0 left-0 right-0 z-30 h-14 wb-topbar flex items-center px-3 gap-2">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="wb-btn-icon p-2 min-w-[44px] min-h-[44px]"
          aria-label="打开菜单"
        >
          <Menu className="w-5 h-5" />
        </button>
        <p className="flex-1 text-sm font-semibold truncate" style={{ color: 'var(--wb-text)' }}>
          RelOS
        </p>
        <ThemeToggle />
      </div>

      {open && (
        <div className="md:hidden fixed inset-0 z-40">
          <button
            type="button"
            className="absolute inset-0 bg-black/50 border-0 w-full h-full cursor-default"
            aria-label="关闭菜单"
            onClick={() => setOpen(false)}
          />
          <div className="absolute top-0 left-0 bottom-0 w-[min(280px,88vw)] shadow-xl">
            <WorkbenchSidebar className="h-full" onNavigate={() => setOpen(false)} />
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="absolute top-3 right-3 wb-btn-icon p-2"
              aria-label="关闭"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div className="hidden md:flex items-center justify-end gap-2 px-4 py-2 wb-topbar flex-shrink-0">
          <ThemeToggle />
        </div>
        <main className="flex-1 overflow-y-auto pt-14 md:pt-0">{children}</main>
      </div>
    </div>
  )
}
