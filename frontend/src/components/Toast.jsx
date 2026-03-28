/**
 * Toast — 轻量通知组件
 */
export default function Toast({ msg, color = 'var(--blue)' }) {
  return (
    <div className="toast" style={{ background: color }}>
      {msg}
    </div>
  )
}
