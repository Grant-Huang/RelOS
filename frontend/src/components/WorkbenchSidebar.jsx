/**
 * 工作台侧栏：运行时 / 知识训练 / 系统 —— 对齐 relos_workbench_v2.html IA
 */
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Activity,
  ClipboardCheck,
  BookOpen,
  UserCog,
  Files,
  Database,
  Bell,
  Factory,
  TrendingUp,
} from 'lucide-react'

function NavItem({ to, end, icon: Icon, label, onNavigate }) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={() => onNavigate?.()}
      className={({ isActive }) => `wb-nav-item ${isActive ? 'wb-nav-item-active' : ''}`}
    >
      <Icon className="w-4 h-4 flex-shrink-0 opacity-80" />
      {label}
    </NavLink>
  )
}

export default function WorkbenchSidebar({ className = '', onNavigate }) {
  return (
    <aside className={`wb-sidebar w-[200px] flex-shrink-0 flex flex-col ${className}`}>
      <div className="px-3.5 py-3 wb-sidebar-logo-border">
        <p className="text-sm font-semibold" style={{ color: 'var(--wb-text)' }}>
          RelOS 知识工作台
        </p>
        <p className="text-[10px] wb-text-muted mt-0.5">v2 · 运行时 + 知识训练</p>
      </div>

      <nav className="flex-1 px-2 py-2 overflow-y-auto">
        <div className="wb-nav-group flex items-center gap-1.5">
          用户前端 <span className="wb-badge-runtime">运行时</span>
        </div>
        <div className="space-y-0.5 mb-3">
          <NavItem to="/runtime/dashboard" end icon={LayoutDashboard} label="运行时仪表盘" onNavigate={onNavigate} />
          <NavItem to="/runtime/automation" icon={Activity} label="自动标注监控" onNavigate={onNavigate} />
          <NavItem to="/runtime/prompt" icon={ClipboardCheck} label="提示标注工作区" onNavigate={onNavigate} />
        </div>

        <div className="wb-nav-group flex items-center gap-1.5">
          专家/管理员 <span className="wb-badge-train">知识训练</span>
        </div>
        <div className="space-y-0.5 mb-3">
          <NavItem to="/knowledge/public" icon={BookOpen} label="公开知识标注" onNavigate={onNavigate} />
          <NavItem to="/knowledge/expert" icon={UserCog} label="专家知识采集" onNavigate={onNavigate} />
          <NavItem to="/knowledge/documents" icon={Files} label="企业文档标注" onNavigate={onNavigate} />
        </div>

        <div className="wb-nav-group">系统监控</div>
        <div className="space-y-0.5 mb-3">
          <NavItem to="/system/kb-status" icon={Database} label="知识库状态" onNavigate={onNavigate} />
        </div>

        <div className="wb-nav-group">分析与演示</div>
        <div className="space-y-0.5">
          <NavItem to="/alarm" icon={Bell} label="告警分析" onNavigate={onNavigate} />
          <NavItem to="/line-efficiency" icon={Factory} label="产线效率" onNavigate={onNavigate} />
          <NavItem to="/strategic-sim" icon={TrendingUp} label="战略模拟" onNavigate={onNavigate} />
        </div>
      </nav>

      <div className="px-3.5 py-2.5 text-[10px] wb-text-muted border-t wb-sidebar-logo-border">
        MVP · 易用性优先
      </div>
    </aside>
  )
}
