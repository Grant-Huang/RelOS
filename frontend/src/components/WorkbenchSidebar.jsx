/**
 * 侧栏：与 docs/relos_workbench_v2.html 侧栏结构、文案、圆点样式一致
 */
import { NavLink } from 'react-router-dom'
import ThemeSwitch from './ThemeSwitch'

function NavBtn({ to, end, dotClass, children }) {
  return (
    <NavLink to={to} end={end} className={({ isActive }) => `nb${isActive ? ' act' : ''}`}>
      <span className={`nb-dot ${dotClass}`} />
      {children}
    </NavLink>
  )
}

export default function WorkbenchSidebar() {
  return (
    <div className="side">
      <div className="logo">
        <div className="logo-n">RelOS 知识工作台</div>
        <div className="logo-s">v2.0 · 双前端设计审查</div>
      </div>

      <div className="grp">
        用户前端 <span className="grp-badge gb-u">运行时</span>
      </div>
      <NavBtn to="/runtime/dashboard" end dotClass="s-on">
        运行时仪表盘
      </NavBtn>
      <NavBtn to="/runtime/automation" dotClass="s-on">
        自动标注监控
      </NavBtn>
      <NavBtn to="/runtime/prompt" dotClass="s-mid">
        提示标注工作区
      </NavBtn>

      <div className="grp">
        专家/管理员 <span className="grp-badge gb-a">知识训练</span>
      </div>
      <NavBtn to="/knowledge/public" dotClass="s-off">
        公开知识标注
      </NavBtn>
      <NavBtn to="/knowledge/expert" dotClass="s-off">
        专家知识采集
      </NavBtn>
      <NavBtn to="/knowledge/documents" dotClass="s-off">
        企业文档标注
      </NavBtn>

      <div className="grp">系统监控</div>
      <NavBtn to="/system/kb-status" dotClass="s-on">
        知识库状态
      </NavBtn>

      <div className="grp">分析与演示</div>
      <NavBtn to="/alarm" dotClass="s-mid">
        告警分析
      </NavBtn>
      <NavBtn to="/line-efficiency" dotClass="s-mid">
        产线效率
      </NavBtn>
      <NavBtn to="/strategic-sim" dotClass="s-mid">
        战略模拟
      </NavBtn>

      <div style={{ flex: 1 }} />
      <ThemeSwitch />
      <div
        style={{
          padding: '10px 14px',
          fontSize: 10,
          color: 'var(--t3)',
          borderTop: '0.5px solid var(--b1)',
        }}
      >
        v2 · 2026.03 · 双前端审查版
      </div>
    </div>
  )
}
