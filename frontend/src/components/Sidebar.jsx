/**
 * Sidebar — 左侧导航栏（原型 v2 风格）
 */
import { NavLink, useLocation } from 'react-router-dom'

const NAV = [
  {
    group: '用户前端',
    badge: { label: '运行时', cls: 'b-blue' },
    items: [
      { to: '/',                label: '运行时仪表盘',   dot: 's-on' },
      { to: '/auto-annotation', label: '自动标注监控',   dot: 's-on' },
      { to: '/hitl',            label: '提示标注工作区', dot: 's-mid' },
    ],
  },
  {
    group: '专家 / 管理员',
    badge: { label: '知识训练', cls: 'b-amber' },
    items: [
      { to: '/public-knowledge', label: '公开知识标注', dot: 's-off' },
      { to: '/expert-knowledge', label: '专家知识采集', dot: 's-off' },
      { to: '/doc-annotation',   label: '企业文档标注', dot: 's-off' },
    ],
  },
  {
    group: '系统监控',
    items: [
      { to: '/kb-status', label: '知识库状态', dot: 's-on' },
    ],
  },
]

export default function Sidebar() {
  const location = useLocation()

  return (
    <aside style={{
      width: 200,
      background: 'var(--bg)',
      borderRight: '0.5px solid var(--b1)',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      height: '100vh',
      overflowY: 'auto',
      position: 'sticky',
      top: 0,
    }}>
      {/* Logo */}
      <div style={{ padding: '13px 14px 8px', borderBottom: '0.5px solid var(--b1)' }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--t1)' }}>RelOS 知识工作台</div>
        <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 2 }}>v2.0 · Sprint 3</div>
      </div>

      {NAV.map((grp) => (
        <div key={grp.group}>
          <div style={{
            padding: '6px 14px 3px',
            fontSize: 10,
            fontWeight: 600,
            color: 'var(--t3)',
            letterSpacing: '0.06em',
            marginTop: 4,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}>
            {grp.group}
            {grp.badge && (
              <span className={`badge ${grp.badge.cls}`} style={{ fontSize: 9 }}>
                {grp.badge.label}
              </span>
            )}
          </div>
          {grp.items.map(({ to, label, dot }) => {
            const isActive = to === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(to)
            return (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 7,
                  width: '100%',
                  padding: '7px 13px',
                  borderLeft: `2.5px solid ${isActive ? 'var(--blue)' : 'transparent'}`,
                  background: isActive ? 'var(--bg2)' : 'none',
                  fontSize: 12,
                  color: isActive ? 'var(--t1)' : 'var(--t2)',
                  fontWeight: isActive ? 500 : 400,
                  textDecoration: 'none',
                  cursor: 'pointer',
                }}
              >
                <span className={`sdot ${dot}`} />
                {label}
              </NavLink>
            )
          })}
        </div>
      ))}

      <div style={{ flex: 1 }} />
      <div style={{
        padding: '10px 14px',
        fontSize: 10,
        color: 'var(--t3)',
        borderTop: '0.5px solid var(--b1)',
      }}>
        v2 · 2026.03 · MVP Sprint 3
      </div>
    </aside>
  )
}
