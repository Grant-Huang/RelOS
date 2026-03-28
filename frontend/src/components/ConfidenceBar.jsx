/**
 * 置信度条 — 与 relos_workbench_v2.html 一致：.cbar + .cfill + cf-high / cf-mid / cf-low
 */
export default function ConfidenceBar({ value = 0, showLabel = true, size = 'md' }) {
  const pct = Math.round((value || 0) * 100)
  const w = Math.min(100, Math.max(0, pct))
  const fillClass = w >= 75 ? 'cf-high' : w >= 50 ? 'cf-mid' : 'cf-low'
  const label = w >= 75 ? '高可信' : w >= 50 ? '中等' : '不确定'
  const textSize = size === 'lg' ? 18 : size === 'sm' ? 11 : 13
  const barH = size === 'lg' ? 8 : size === 'sm' ? 4 : 6

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', minWidth: 0 }}>
      <div className="cbar" style={{ height: barH, flex: 1, minWidth: 0 }}>
        <div className={`cfill ${fillClass}`} style={{ width: `${w}%` }} />
      </div>
      <span className="tabular-nums" style={{ fontWeight: 600, fontSize: textSize, color: 'var(--t1)', flexShrink: 0 }}>
        {pct}%
      </span>
      {showLabel ? (
        <span className={`badge ${w >= 75 ? 'b-green' : w >= 50 ? 'b-amber' : 'b-red'}`} style={{ flexShrink: 0 }}>
          {label}
        </span>
      ) : null}
    </div>
  )
}
