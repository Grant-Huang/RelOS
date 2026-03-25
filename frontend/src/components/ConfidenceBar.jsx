/**
 * ConfidenceBar — 置信度可视化组件
 * 输入：value (0.0–1.0)
 * 输出：百分比文字 + 颜色色块条 + 中文标签
 */
export default function ConfidenceBar({ value = 0, showLabel = true, size = 'md' }) {
  const pct = Math.round(value * 100)

  const color =
    pct >= 75 ? '#16A34A' :  // 高可信 - 绿
    pct >= 50 ? '#EA580C' :  // 中等 - 橙
    '#DC2626'                 // 不确定 - 红

  const label =
    pct >= 75 ? '高可信' :
    pct >= 50 ? '中等' :
    '不确定'

  const textSize = size === 'lg' ? 'text-2xl' : size === 'sm' ? 'text-xs' : 'text-sm'
  const barH = size === 'lg' ? 'h-3' : size === 'sm' ? 'h-1.5' : 'h-2'

  // 5 格色块条，每格 20%
  const blocks = Array.from({ length: 5 }, (_, i) => ({
    filled: pct >= (i + 1) * 20,
  }))

  return (
    <div className="flex items-center gap-3">
      {/* 色块条 */}
      <div className="flex gap-0.5">
        {blocks.map((b, i) => (
          <div
            key={i}
            className={`${barH} w-5 rounded-sm transition-all duration-300`}
            style={{ backgroundColor: b.filled ? color : '#374151' }}
          />
        ))}
      </div>

      {/* 百分比 */}
      <span className={`font-bold tabular-nums ${textSize}`} style={{ color }}>
        {pct}%
      </span>

      {/* 标签 */}
      {showLabel && (
        <span
          className="text-xs px-2 py-0.5 rounded-full font-medium"
          style={{ backgroundColor: color + '22', color }}
        >
          {label}
        </span>
      )}
    </div>
  )
}
