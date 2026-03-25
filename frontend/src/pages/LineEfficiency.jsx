/**
 * LineEfficiency — 产线效率瓶颈分析（场景 S-07）
 * 同时展示：跨部门协同（S-08）、异常处理效率（S-09）
 */
import { useEffect, useState } from 'react'
import { Factory, AlertTriangle, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { getLineEfficiency, getCrossDeptAnalysis, getIssueResolution } from '../api/client'

// mock 数据（后端不可用时降级）
const MOCK_LINE = {
  lines: [
    { line_id: 'line-L1', name: '冲压线', efficiency_pct: 92, status: 'normal' },
    { line_id: 'line-L2', name: '焊接线', efficiency_pct: 64, status: 'bottleneck' },
    { line_id: 'line-L3', name: '装配线', efficiency_pct: 81, status: 'normal' },
  ],
  bottleneck_line_id: 'line-L2',
  bottleneck_machine_id: 'machine-M3',
  bottleneck_contribution_pct: 42.0,
  root_cause_path: [
    '设备 machine-M3 停机频繁',
    '告警：焊接过热告警（7天内 9 次，环比 +80%）',
    '产线 line-L2 效率损失 28%',
    '占总延误贡献 42%',
  ],
}

const MOCK_RESOLUTION = {
  issue_type_summary: [
    { display_name: '轴承磨损', avg_resolution_hours: 2.7, status: 'slow' },
    { display_name: '电气故障', avg_resolution_hours: 1.1, status: 'normal' },
    { display_name: '冷却系统', avg_resolution_hours: 0.7, status: 'normal' },
  ],
  shift_comparison: { night_avg_hours: 3.0, day_avg_hours: 1.3, night_vs_day_ratio: 2.31 },
  insight: '夜班处理时间比白班平均长 131%，轴承类问题最为突出',
}

const MOCK_CROSS = {
  causal_chain: [
    '供应商 A（华盛钢材）准时率仅 43%',
    'Q235 钢板库存降至安全库存 22%',
    '2 个工单因缺料被迫推迟',
    '平均每工单延误 3 天，影响交付承诺',
  ],
  delay_attribution: { '采购部门': 47.8, '生产部门': 21.7, '计划部门': 30.5 },
  total_delay_days: 6,
}

function LineBar({ line, isBottleneck, onClick, expanded }) {
  const color = isBottleneck ? '#DC2626' : line.efficiency_pct >= 85 ? '#16A34A' : '#EA580C'

  return (
    <div className="mb-3">
      <button
        onClick={onClick}
        className={`w-full rounded-xl border p-4 text-left transition-all ${
          isBottleneck ? 'border-red-800 bg-red-900/10' : 'border-gray-700 bg-surface hover:border-gray-500'
        }`}
      >
        <div className="flex items-center justify-between mb-3">
          <div>
            <span className="font-semibold text-white">{line.name || line.line_id}</span>
            {isBottleneck && (
              <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-red-900 text-red-400 border border-red-800">
                瓶颈
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-2xl font-bold tabular-nums" style={{ color }}>
              {line.efficiency_pct}%
            </span>
            {isBottleneck
              ? (expanded ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />)
              : null
            }
          </div>
        </div>
        <div className="w-full bg-gray-800 rounded-full h-2.5">
          <div
            className="h-2.5 rounded-full transition-all duration-700"
            style={{ width: `${line.efficiency_pct}%`, backgroundColor: color }}
          />
        </div>
      </button>

      {/* 瓶颈详情（可折叠） */}
      {isBottleneck && expanded && (
        <div className="mx-4 border-x border-b border-red-800 rounded-b-xl bg-red-900/10 px-5 py-4">
          <p className="text-xs text-gray-500 mb-3">根因路径</p>
          <ol className="space-y-2">
            {MOCK_LINE.root_cause_path.map((step, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <span className="w-5 h-5 rounded-full bg-red-900 border border-red-700 text-xs text-red-400 font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                  {i + 1}
                </span>
                <span className="text-sm text-gray-300">{step}</span>
              </li>
            ))}
          </ol>
          <div className="mt-3 pt-3 border-t border-red-900 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <span className="text-sm text-red-300">
              瓶颈贡献度：<strong>{MOCK_LINE.bottleneck_contribution_pct}%</strong> 的总延误
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

export default function LineEfficiency() {
  const [lineData, setLineData] = useState(null)
  const [resolutionData, setResolutionData] = useState(null)
  const [crossData, setCrossData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [useMock, setUseMock] = useState(false)
  const [expandedLine, setExpandedLine] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const [line, res, cross] = await Promise.all([
        getLineEfficiency().catch(() => null),
        getIssueResolution().catch(() => null),
        getCrossDeptAnalysis().catch(() => null),
      ])
      setLineData(line || MOCK_LINE)
      setResolutionData(res || MOCK_RESOLUTION)
      setCrossData(cross || MOCK_CROSS)
      setUseMock(!line && !res && !cross)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const ld = lineData || MOCK_LINE
  const rd = resolutionData || MOCK_RESOLUTION
  const cd = crossData || MOCK_CROSS

  const resolutionBarData = rd.issue_type_summary?.map(d => ({
    name: d.display_name,
    hours: d.avg_resolution_hours,
    slow: d.status === 'slow',
  })) || []

  const attrData = Object.entries(cd.delay_attribution || {}).map(([name, pct]) => ({ name, pct }))

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* 页头 */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <Factory className="w-6 h-6 text-blue-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">中层运营分析</h1>
            <p className="text-gray-500 text-sm">场景 S-07/08/09 · 产线效率 / 跨部门协同 / 异常处理</p>
          </div>
        </div>
        <button onClick={load} disabled={loading} className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-700 text-gray-400 hover:text-white text-sm transition-colors">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {useMock && (
        <div className="mb-6 bg-blue-900/30 border border-blue-800 rounded-xl px-5 py-3 text-sm text-blue-300 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          使用演示数据（请先运行 python scripts/seed_demo_scenarios.py）
        </div>
      )}

      {/* S-07：产线效率 */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold text-white mb-4">产线效率看板（S-07）</h2>
        <div>
          {ld.lines?.map((line) => {
            const isBottleneck = line.line_id === ld.bottleneck_line_id || line.status === 'bottleneck'
            return (
              <LineBar
                key={line.line_id}
                line={line}
                isBottleneck={isBottleneck}
                expanded={expandedLine === line.line_id}
                onClick={() => setExpandedLine(
                  isBottleneck
                    ? (expandedLine === line.line_id ? null : line.line_id)
                    : null
                )}
              />
            )
          })}
        </div>
      </section>

      {/* S-08/09：两列布局 */}
      <div className="grid grid-cols-2 gap-6">
        {/* S-09：异常处理效率 */}
        <div className="bg-surface rounded-xl border border-gray-700 p-5">
          <h2 className="text-sm font-semibold text-gray-400 mb-4 uppercase tracking-wider">异常处理效率（S-09）</h2>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={resolutionBarData} layout="vertical" margin={{ left: 10 }}>
              <XAxis type="number" tick={{ fill: '#6B7280', fontSize: 11 }} unit="h" />
              <YAxis type="category" dataKey="name" tick={{ fill: '#D1D5DB', fontSize: 12 }} width={70} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#F9FAFB' }}
                formatter={(v) => [`${v}h`, '平均处理时长']}
              />
              <Bar dataKey="hours" radius={[0, 4, 4, 0]}>
                {resolutionBarData.map((entry, i) => (
                  <Cell key={i} fill={entry.slow ? '#DC2626' : '#16A34A'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* 班次对比 */}
          {rd.shift_comparison && (
            <div className="mt-4 bg-bg rounded-lg p-3 border border-gray-800">
              <p className="text-xs text-gray-500 mb-2">班次对比</p>
              <div className="flex justify-between text-sm">
                <div>
                  <p className="text-gray-500 text-xs">夜班</p>
                  <p className="text-red-400 font-bold">{rd.shift_comparison.night_avg_hours}h</p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-gray-600">慢</p>
                  <p className="text-red-400 font-bold text-lg">{rd.shift_comparison.night_vs_day_ratio}×</p>
                </div>
                <div className="text-right">
                  <p className="text-gray-500 text-xs">白班</p>
                  <p className="text-green-400 font-bold">{rd.shift_comparison.day_avg_hours}h</p>
                </div>
              </div>
            </div>
          )}

          {rd.insight && (
            <p className="mt-3 text-xs text-gray-500 italic">{rd.insight}</p>
          )}
        </div>

        {/* S-08：跨部门协同 */}
        <div className="bg-surface rounded-xl border border-gray-700 p-5">
          <h2 className="text-sm font-semibold text-gray-400 mb-4 uppercase tracking-wider">跨部门协同（S-08）</h2>

          {/* 因果链 */}
          <div className="space-y-2 mb-4">
            {cd.causal_chain?.map((step, i) => (
              <div key={i} className="flex items-start gap-2.5">
                <div className="w-5 h-5 rounded-full bg-orange-900 border border-orange-700 text-xs text-orange-400 font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                  {i + 1}
                </div>
                <p className="text-xs text-gray-300 leading-relaxed">{step}</p>
              </div>
            ))}
          </div>

          {/* 责任归因 */}
          {attrData.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 mb-2">延误责任分布</p>
              <ResponsiveContainer width="100%" height={120}>
                <BarChart data={attrData} margin={{ left: 0 }}>
                  <XAxis dataKey="name" tick={{ fill: '#9CA3AF', fontSize: 11 }} />
                  <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} unit="%" domain={[0, 60]} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: 8 }}
                    formatter={(v) => [`${v}%`, '责任占比']}
                  />
                  <Bar dataKey="pct" fill="#EA580C" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {cd.total_delay_days && (
            <p className="mt-2 text-xs text-gray-500">
              总延误影响：<strong className="text-orange-400">{cd.total_delay_days} 天</strong>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
