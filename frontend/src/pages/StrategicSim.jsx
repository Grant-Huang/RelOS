/**
 * StrategicSim — 战略决策模拟（场景 S-12）
 * 同时展示资源配置优化（S-11）
 */
import { useState, useCallback } from 'react'
import { TrendingUp, AlertTriangle, CheckCircle, Zap } from 'lucide-react'
import { runStrategicSimulation, getResourceOptimization } from '../api/client'
import ConfidenceBar from '../components/ConfidenceBar'

const RISK_COLORS = { high: '#DC2626', medium: '#EA580C', low: '#16A34A' }

// mock 资源配置数据
const MOCK_RESOURCES = {
  recommendations: [
    { rank: 1, resource_name: '设备维护团队', roi_pct: 35, investment_rmb: 360000, impact_description: '可减少交付延误 41%' },
    { rank: 2, resource_name: '供应商管理专员', roi_pct: 28, investment_rmb: 180000, impact_description: '可减少交付延误 31%' },
    { rank: 3, resource_name: '夜班专项培训', roi_pct: 22, investment_rmb: 80000, impact_description: '可提升夜班效率 35%' },
  ],
  priority_action: '优先投入：设备维护团队（ROI 最高，预计 8 个月回本）',
}

function RiskChangeRow({ label, change, color }) {
  const isRise = change > 0
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-gray-800 last:border-0">
      <span className="text-sm text-gray-400">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-lg font-bold tabular-nums" style={{ color }}>
          {isRise ? '+' : ''}{change.toFixed(1)}%
        </span>
        <span className="text-lg" style={{ color }}>{isRise ? '↑' : '↓'}</span>
      </div>
    </div>
  )
}

export default function StrategicSim() {
  const [expansion, setExpansion] = useState(30)
  const [simResult, setSimResult] = useState(null)
  const [resources, setResources] = useState(null)
  const [loading, setLoading] = useState(false)
  const [resLoading, setResLoading] = useState(false)

  const runSim = useCallback(async () => {
    setLoading(true)
    try {
      const data = await runStrategicSimulation(expansion)
      setSimResult(data)
    } catch {
      // mock 降级
      setSimResult({
        expansion_pct: expansion,
        delivery_risk_change_pct: +(expansion * 0.9).toFixed(1),
        failure_rate_change_pct: +(expansion * 0.6).toFixed(1),
        quality_risk_change_pct: +(expansion * 0.4).toFixed(1),
        risk_level: expansion > 25 ? 'high' : expansion > 15 ? 'medium' : 'low',
        causal_chain: [
          `订单量 +${expansion}%`,
          `产线负载：70% → ${Math.min(99, 70 + expansion * 0.7).toFixed(0)}%（+${(expansion * 0.7).toFixed(0)}%）`,
          `设备故障率预计上升 ${(expansion * 0.6).toFixed(0)}%（弹性系数 1.8）`,
          `质量缺陷率预计上升 ${(expansion * 0.4).toFixed(0)}%`,
          `交付风险综合上升 ${(expansion * 0.9).toFixed(0)}%`,
        ],
        recommendations: [
          '建议扩产前完成 M3 维修保养（消除当前 18.5h/周停机隐患）',
          '将供应商 A 准时率提升至 80% 以上，否则扩产后缺料风险翻倍',
          '夜班增配有经验维修工',
        ],
      })
    } finally {
      setLoading(false)
    }
  }, [expansion])

  const loadResources = async () => {
    setResLoading(true)
    try {
      const data = await getResourceOptimization()
      setResources(data)
    } catch {
      setResources(MOCK_RESOURCES)
    } finally {
      setResLoading(false)
    }
  }

  const riskColor = RISK_COLORS[simResult?.risk_level] || '#6B7280'
  const riskText = simResult?.risk_level === 'high' ? '高风险' : simResult?.risk_level === 'medium' ? '中等风险' : '可接受'

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* 页头 */}
      <div className="flex items-center gap-3 mb-8">
        <TrendingUp className="w-6 h-6 text-blue-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">高层决策分析</h1>
          <p className="text-gray-500 text-sm">场景 S-11/12 · 资源配置优化 + 战略扩产模拟</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-8">
        {/* 左：战略模拟（S-12） */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">扩产影响模拟（S-12）</h2>

          {/* 滑条 */}
          <div className="bg-surface rounded-xl border border-gray-700 p-6 mb-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm text-gray-400">扩产比例</p>
              <span className="text-3xl font-bold text-blue-400 tabular-nums">+{expansion}%</span>
            </div>
            <input
              type="range"
              min="5" max="60" step="5"
              value={expansion}
              onChange={(e) => setExpansion(Number(e.target.value))}
              className="w-full accent-blue-500 mb-2"
            />
            <div className="flex justify-between text-xs text-gray-600">
              <span>保守 +5%</span>
              <span>激进 +60%</span>
            </div>

            {/* 预警色阶 */}
            <div className="mt-4 flex gap-1 text-xs">
              {[5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60].map(v => (
                <div
                  key={v}
                  className={`flex-1 h-1.5 rounded-full transition-all ${
                    v <= expansion
                      ? v <= 15 ? 'bg-confidence-high' : v <= 25 ? 'bg-confidence-mid' : 'bg-confidence-low'
                      : 'bg-gray-800'
                  }`}
                />
              ))}
            </div>

            <button
              onClick={runSim}
              disabled={loading}
              className="mt-5 w-full flex items-center justify-center gap-2 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 transition-colors font-semibold text-white"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  模拟中...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  运行模拟
                </>
              )}
            </button>
          </div>

          {/* 模拟结果 */}
          {simResult && (
            <div className="space-y-4">
              {/* 综合风险等级 */}
              <div
                className="rounded-xl border px-6 py-4 flex items-center justify-between"
                style={{ borderColor: riskColor + '66', backgroundColor: riskColor + '11' }}
              >
                <div>
                  <p className="text-sm text-gray-400">综合风险评级</p>
                  <p className="text-white text-sm mt-1">扩产 +{simResult.expansion_pct}% 的预期影响</p>
                </div>
                <span className="text-2xl font-bold" style={{ color: riskColor }}>{riskText}</span>
              </div>

              {/* 风险变化数据 */}
              <div className="bg-surface rounded-xl border border-gray-700 px-5 py-4">
                <p className="text-xs text-gray-500 mb-3 uppercase tracking-wider">关键风险指标变化</p>
                <RiskChangeRow label="交付风险" change={simResult.delivery_risk_change_pct} color="#DC2626" />
                <RiskChangeRow label="设备故障率" change={simResult.failure_rate_change_pct} color="#EA580C" />
                <RiskChangeRow label="质量缺陷率" change={simResult.quality_risk_change_pct} color="#EA580C" />
              </div>

              {/* 因果链 */}
              <div className="bg-surface rounded-xl border border-gray-700 px-5 py-4">
                <p className="text-xs text-gray-500 mb-3 uppercase tracking-wider">影响路径</p>
                <ol className="space-y-2">
                  {simResult.causal_chain?.map((step, i) => (
                    <li key={i} className="flex items-start gap-2.5">
                      <span className="w-5 h-5 rounded-full bg-blue-900 border border-blue-700 text-xs text-blue-400 font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                        {i + 1}
                      </span>
                      <span className="text-sm text-gray-300">{step}</span>
                    </li>
                  ))}
                </ol>
              </div>

              {/* 建议 */}
              {simResult.recommendations?.length > 0 && (
                <div className="bg-surface rounded-xl border border-gray-700 px-5 py-4">
                  <p className="text-xs text-gray-500 mb-3 uppercase tracking-wider">扩产前建议</p>
                  <ul className="space-y-2">
                    {simResult.recommendations.map((rec, i) => (
                      <li key={i} className="flex items-start gap-2.5">
                        <AlertTriangle className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
                        <span className="text-sm text-gray-300">{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 右：资源配置（S-11） */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">资源配置优化（S-11）</h2>
            {!resources && (
              <button
                onClick={loadResources}
                disabled={resLoading}
                className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
              >
                {resLoading ? '加载中...' : '加载建议'}
              </button>
            )}
          </div>

          {!resources && !resLoading && (
            <div className="bg-surface rounded-xl border border-dashed border-gray-700 p-8 text-center">
              <TrendingUp className="w-8 h-8 text-gray-600 mx-auto mb-3" />
              <p className="text-gray-500 text-sm">点击"加载建议"获取资源配置优化方案</p>
              <button
                onClick={loadResources}
                className="mt-4 px-4 py-2 rounded-lg bg-blue-600/30 text-blue-400 text-sm hover:bg-blue-600/50 transition-colors border border-blue-800"
              >
                获取建议
              </button>
            </div>
          )}

          {resLoading && (
            <div className="space-y-3">
              {[1, 2, 3].map(i => <div key={i} className="bg-surface rounded-xl border border-gray-700 h-28 animate-pulse" />)}
            </div>
          )}

          {resources && (
            <div className="space-y-4">
              {resources.recommendations?.map((rec, i) => (
                <div key={i} className="bg-surface rounded-xl border border-gray-700 p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="w-6 h-6 rounded-full bg-blue-900 border border-blue-700 text-xs text-blue-400 font-bold flex items-center justify-center">
                          {rec.rank}
                        </span>
                        <p className="font-semibold text-white">{rec.resource_name}</p>
                      </div>
                      <p className="text-sm text-gray-400">{rec.impact_description}</p>
                    </div>
                    <div className="text-right flex-shrink-0 ml-4">
                      <p className="text-2xl font-bold text-confidence-high tabular-nums">{rec.roi_pct}%</p>
                      <p className="text-xs text-gray-500">ROI</p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-500">
                      投入：¥{(rec.investment_rmb / 10000).toFixed(0)} 万
                    </span>
                    <div className="w-32">
                      <ConfidenceBar value={rec.roi_pct / 100} size="sm" showLabel={false} />
                    </div>
                  </div>
                </div>
              ))}

              {resources.priority_action && (
                <div className="bg-blue-900/20 border border-blue-800 rounded-xl px-5 py-4 flex items-start gap-3">
                  <CheckCircle className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-blue-300">{resources.priority_action}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
