/**
 * 布局：对齐 docs/relos_workbench_v2.html（.app + .side + .main）
 */
import WorkbenchSidebar from './WorkbenchSidebar'

export default function Layout({ children }) {
  return (
    <div className="app">
      <WorkbenchSidebar />
      <main className="main">{children}</main>
    </div>
  )
}
