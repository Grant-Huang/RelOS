/**
 * Dashboard — 企业态势总览
 * 展示：风险雷达（S-10）、图谱统计、快捷入口
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar,
  ResponsiveContainer, Tooltip,
} from 'recharts'
import { Bell, AlertTriangle, TrendingUp, Database, ArrowRight, RefreshCw } from 'lucide-react'
import { getRiskRadar, getMetrics } from '../api/client'

const RISK_COLORS = { high: '#DC2626', medium: '#EA580C', low: '#16A34A' }
const TREND_ICONS = { rising: '↑', stable: '→', falling: '↓' }
const TREND_COLORS = { rising: 'text-red-400', stable: 'text-gray-400', falling: 'text-green-400' }

function RiskDomainCard({ domain }) {
  const color = RISK_COLORS[domain.level] || '#6B7280'
  const trendIcon = TREND_ICONS[domain.trend] || '→'
  const trendColor = TREND_COLORS[domain.trend] || 'text-gray-400'

  return (
    <div className="bg-surface rounded-xl border border-gray-700 p-5">
      <div className="flex items-start justify-between mb-3">
        <p className="text-sm text-gray-400">{domain.name}</p>
        <span className={`text-lg font-bold ${trendColor}`}>{trendIcon}</span>
      </div>
      {/* 风险评分 */}
      <p className="text-4xl font-bold tabular-nums mb-3" style={{ color }}>
        {domain.score_pct}
        <span className="text-xl text-gray-500">%</span>
      </p>
      {/* 进度条 */}
      <div className="w-full bg-gray-800 rounded-full h-2 mb-2">
        <div
          className="h-2 rounded-full transition-all duration-700"
          style={{ width: `${domain.score_pct}%`, backgroundColor: color }}
        />
      </div>
      <span
        className="inline-block text-xs px-2 py-0.5 rounded-full font-medium"
        style={{ backgroundColor: color + '22', color }}
      >
        {domain.level === 'high' ? '高风险' : domain.level === 'medium' ? '中等风险' : '低风险'}
      </span>
    </div>
  )
}

function CausalChain({ items }) {
  return (
    <ol className="space-y-2">
      {items.map((step, i) => (
        <li key={i} className="flex items-start gap-3">
          <div className="flex flex-col items-center mt-0.5">
            <div className="w-6 h-6 rounded-full bg-red-900 border border-red-700 flex items-center justify-center text-xs font-bold text-red-400 flex-shrink-0">
              {i + 1}
            </div>
            {i < items.length - 1 && (
              <div className="w-px h-4 bg-gray-700 my-1" />
            )}
          </div>
          <p className="text-sm text-gray-300 leading-relaxed pt-0.5">{step}</p>
        </li>
      ))}
    </ol>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [riskData, setRiskData] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [risk, met] = await Promise.all([
        getRiskRadar().catch(() => null),
        getMetrics().catch(() => null),
      ])
      setRiskData(risk)
      setMetrics(met)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // 雷达图数据
  const radarData = riskData?.risk_domains?.map(d => ({
    subject: d.name.replace('风险', ''),
    value: d.score_pct,
    fullMark: 100,
  })) || []

  const overallLevel = riskData?.overall_risk_level
  const overallColor = RISK_COLORS[overallLevel] || '#6B7280'
  const overallText = overallLevel === 'high' ? '高风险' : overallLevel === 'medium' ? '中等' : '正常'

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* 页头 */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">企业态势总览</h1>
          <p className="text-gray-500 text-sm mt-1">
            {new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })}
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-700 text-gray-400 hover:text-white hover:border-gray-500 transition-colors text-sm"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {error && (
        <div className="mb-6 bg-red-900/30 border border-red-800 rounded-xl px-5 py-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0" />
          <div>
            <p className="text-red-300 font-medium">无法连接后端服务</p>
            <p className="text-red-500 text-sm">{error} — 请确认 uvicorn 已启动（端口 8000）</p>
          </div>
        </div>
      )}

      {/* 总体风险状态 */}
      {riskData && (
        <div
          className="mb-6 rounded-xl border px-6 py-5 flex items-center justify-between"
          style={{ borderColor: overallColor + '66', backgroundColor: overallColor + '11' }}
        >
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-6 h-6" style={{ color: overallColor }} />
            <div>
              <p className="text-white font-semibold">当前整体风险等级</p>
              <p className="text-sm text-gray-400">
                最高风险：{riskData.top_risk?.name}（{riskData.top_risk?.score_pct}%）
              </p>
            </div>
          </div>
          <span
            className="text-2xl font-bold px-4 py-1 rounded-lg"
            style={{ color: overallColor, backgroundColor: overallColor + '22' }}
          >
            {overallText}
          </span>
        </div>
      )}

      {/* 三大风险域 */}
      {riskData?.risk_domains && (
        <div className="grid grid-cols-3 gap-4 mb-8">
          {riskData.risk_domains.map((d, i) => (
            <RiskDomainCard key={i} domain={d} />
          ))}
        </div>
      )}

      {/* 中间：雷达图 + 因果链 */}
      {riskData && (
        <div className="grid grid-cols-2 gap-6 mb-8">
          {/* 雷达图 */}
          <div className="bg-surface rounded-xl border border-gray-700 p-6">
            <h2 className="text-sm font-semibold text-gray-400 mb-4 uppercase tracking-wider">风险雷达图</h2>
            {radarData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#374151" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: '#9CA3AF', fontSize: 12 }} />
                  <Radar
                    name="风险"
                    dataKey="value"
                    stroke="#DC2626"
                    fill="#DC2626"
                    fillOpacity={0.25}
                    strokeWidth={2}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
                    labelStyle={{ color: '#F9FAFB' }}
                    itemStyle={{ color: '#9CA3AF' }}
                    formatter={(v) => [`${v}%`, '风险评分']}
                  />
                </RadarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-gray-600">
                暂无数据
              </div>
            )}
          </div>

          {/* 顶级风险因果链 */}
          <div className="bg-surface rounded-xl border border-gray-700 p-6">
            <h2 className="text-sm font-semibold text-gray-400 mb-4 uppercase tracking-wider">
              最高风险因果链
            </h2>
            {riskData.top_risk_causal_chain?.length > 0 ? (
              <CausalChain items={riskData.top_risk_causal_chain} />
            ) : (
              <p className="text-gray-600 text-sm">暂无因果链数据</p>
            )}
          </div>
        </div>
      )}

      {/* 图谱统计 */}
      {metrics && (
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[
            { label: '关系总数', value: metrics.total_relations ?? metrics.relations_count ?? '—', icon: Database, color: 'text-blue-400' },
            { label: '活跃关系', value: metrics.active_relations ?? '—', icon: Database, color: 'text-green-400' },
            { label: '待审核', value: metrics.pending_review ?? '—', icon: AlertTriangle, color: 'text-yellow-400' },
            { label: '图谱节点', value: metrics.total_nodes ?? '—', icon: TrendingUp, color: 'text-purple-400' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-surface rounded-xl border border-gray-700 p-5">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs text-gray-500">{label}</p>
                <Icon className={`w-4 h-4 ${color}`} />
              </div>
              <p className={`text-3xl font-bold tabular-nums ${color}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* 快捷入口 */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: '分析告警', desc: '输入告警码，获取根因推荐', icon: Bell, to: '/alarm', color: 'text-red-400' },
          { label: '审核待定关系', desc: '处理 LLM 抽取的待审核关系', icon: AlertTriangle, to: '/hitl', color: 'text-yellow-400' },
          { label: '战略模拟', desc: '模拟扩产对风险的影响', icon: TrendingUp, to: '/strategic-sim', color: 'text-blue-400' },
        ].map(({ label, desc, icon: Icon, to, color }) => (
          <button
            key={to}
            onClick={() => navigate(to)}
            className="bg-surface rounded-xl border border-gray-700 p-5 text-left hover:border-gray-500 hover:bg-white/5 transition-all group"
          >
            <Icon className={`w-6 h-6 ${color} mb-3`} />
            <p className="font-semibold text-white mb-1">{label}</p>
            <p className="text-sm text-gray-500">{desc}</p>
            <div className="flex items-center gap-1 mt-3 text-xs text-gray-600 group-hover:text-gray-400 transition-colors">
              进入 <ArrowRight className="w-3 h-3" />
            </div>
          </button>
        ))}
      </div>

      {loading && !riskData && (
        <div className="fixed inset-0 bg-bg/70 flex items-center justify-center">
          <div className="bg-surface rounded-xl border border-gray-700 px-8 py-6 flex items-center gap-4">
            <RefreshCw className="w-6 h-6 text-blue-400 animate-spin" />
            <p className="text-gray-300">正在加载数据...</p>
          </div>
        </div>
      )}
    </div>
  )
}
