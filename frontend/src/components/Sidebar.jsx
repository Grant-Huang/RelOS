/**
 * Sidebar — 左侧导航栏
 */
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Bell,
  ClipboardCheck,
  UserCog,
  MessagesSquare,
  Factory,
  TrendingUp,
  Activity,
} from 'lucide-react'

const NAV_ITEMS = [
  { to: '/', label: '总览', icon: LayoutDashboard, end: true },
  { to: '/alarm', label: '告警分析', icon: Bell },
  { to: '/hitl', label: '待审核关系', icon: ClipboardCheck },
  { to: '/expert-init', label: '专家初始化', icon: UserCog },
  { to: '/interview', label: '访谈微卡片', icon: MessagesSquare },
  { to: '/line-efficiency', label: '产线效率', icon: Factory },
  { to: '/strategic-sim', label: '战略模拟', icon: TrendingUp },
]

export default function Sidebar({ className = '', onNavigate }) {
  return (
    <aside className={`w-56 flex-shrink-0 bg-surface border-r border-gray-700 flex flex-col ${className}`}>
      {/* Logo */}
      <div className="px-5 py-5 border-b border-gray-700">
        <div className="flex items-center gap-2.5">
          <Activity className="w-6 h-6 text-blue-400" />
          <div>
            <p className="text-white font-bold text-base leading-none">RelOS</p>
            <p className="text-gray-500 text-xs mt-0.5">关系操作系统</p>
          </div>
        </div>
      </div>

      {/* 导航 */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={() => onNavigate?.()}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white hover:bg-white/5'
              }`
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* 底部版本信息 */}
      <div className="px-5 py-4 border-t border-gray-700">
        <p className="text-xs text-gray-600">MVP v0.3.0</p>
        <p className="text-xs text-gray-600">Sprint 3 · 2026-03</p>
      </div>
    </aside>
  )
}
