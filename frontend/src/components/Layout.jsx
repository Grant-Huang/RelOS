/**
 * Layout — 应用主布局（侧边栏 + 主内容区）
 */
import { useState } from 'react'
import { Menu, X } from 'lucide-react'
import Sidebar from './Sidebar'

export default function Layout({ children }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      {/* Desktop Sidebar */}
      <Sidebar className="hidden md:flex" />

      {/* Mobile Top Bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-30 h-14 bg-surface border-b border-gray-700 flex items-center px-4">
        <button
          onClick={() => setOpen(true)}
          className="p-2 rounded-lg border border-gray-700 bg-bg text-gray-200"
        >
          <Menu className="w-5 h-5" />
        </button>
        <p className="ml-3 text-white font-semibold">RelOS</p>
      </div>

      {/* Mobile Drawer */}
      {open && (
        <div className="md:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <div className="absolute top-0 left-0 bottom-0 w-72">
            <Sidebar
              className="h-full"
              onNavigate={() => setOpen(false)}
            />
            <button
              onClick={() => setOpen(false)}
              className="absolute top-4 right-4 p-2 rounded-lg border border-gray-700 bg-bg text-gray-200"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      <main className="flex-1 overflow-y-auto pt-14 md:pt-0">
        {children}
      </main>
    </div>
  )
}
