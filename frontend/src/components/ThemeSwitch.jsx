/**
 * 浅色 / 深色切换，样式与 workbench v2 的 .btn 一致
 */
import { useTheme } from '../context/ThemeContext'

export default function ThemeSwitch() {
  const { theme, setTheme } = useTheme()

  return (
    <div className="theme-switch">
      <div className="theme-switch-label">外观</div>
      <div className="theme-switch-row">
        <button
          type="button"
          className={`btn btn-sm theme-switch-btn${theme === 'light' ? ' theme-switch-btn-active' : ''}`}
          onClick={() => setTheme('light')}
        >
          浅色
        </button>
        <button
          type="button"
          className={`btn btn-sm theme-switch-btn${theme === 'dark' ? ' theme-switch-btn-active' : ''}`}
          onClick={() => setTheme('dark')}
        >
          深色
        </button>
      </div>
    </div>
  )
}
