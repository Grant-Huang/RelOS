/**
 * 运行时仪表盘：有什么事、建议什么、下一步去哪（易用性优先）
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, ClipboardCheck, Activity, ChevronDown, ChevronUp, RefreshCw, AlertTriangle } from 'lucide-react'
import { getMetrics, getRiskRadar } from '../../api/client'

export default function RuntimeDashboard() {
  const navigate = useNavigate()
  const [metrics, setMetrics] = useState(null)
  const [risk, setRisk] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expandMetrics, setExpandMetrics] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [m, r] = await Promise.all([getMetrics().catch(() => null), getRiskRadar().catch(() => null)])
      setMetrics(m)
      setRisk(r)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const pending = metrics?.pending_review_count ?? '—'
  const totalRel = metrics?.total_relations ?? '—'

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl md:text-2xl font-semibold mb-1" style={{ color: 'var(--wb-text)' }}>
            运行时仪表盘
          </h1>
          <p className="text-sm wb-text-muted">操作员视角 · 现在有什么事、系统建议什么、我要做什么决定</p>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="wb-btn-ghost flex items-center gap-2 text-sm min-h-[44px]"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <button
          type="button"
          onClick={() => navigate('/runtime/prompt')}
          className="wb-card p-4 text-left hover:opacity-95 transition-opacity min-h-[88px]"
        >
          <p className="text-2xl font-semibold tabular-nums" style={{ color: 'var(--wb-amber)' }}>
            {pending}
          </p>
          <p className="text-xs wb-text-muted mt-1">待提示确认（0.50–0.79）</p>
        </button>
        <div className="wb-card p-4 min-h-[88px]">
          <p className="text-2xl font-semibold tabular-nums wb-text-secondary">{totalRel}</p>
          <p className="text-xs wb-text-muted mt-1">图谱关系总数</p>
        </div>
        <div className="wb-card p-4 min-h-[88px] col-span-2 md:col-span-1">
          <p className="text-sm font-medium wb-text-secondary line-clamp-2">
            {risk?.top_risk?.name ? `当前最高风险：${risk.top_risk.name}` : '风险数据未加载'}
          </p>
          <p className="text-xs wb-text-muted mt-1">详见下方折叠区</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-8">
        <button
          type="button"
          onClick={() => navigate('/alarm')}
          className="wb-card p-5 text-left border-2 border-transparent hover:border-[var(--wb-blue)] min-h-[100px]"
        >
          <Bell className="w-6 h-6 mb-2" style={{ color: 'var(--wb-red)' }} />
          <p className="font-semibold" style={{ color: 'var(--wb-text)' }}>
            分析告警
          </p>
          <p className="text-sm wb-text-muted mt-1">获取根因推荐与流式解释</p>
        </button>
        <button
          type="button"
          onClick={() => navigate('/runtime/automation')}
          className="wb-card p-5 text-left border-2 border-transparent hover:border-[var(--wb-green)] min-h-[100px]"
        >
          <Activity className="w-6 h-6 mb-2" style={{ color: 'var(--wb-green)' }} />
          <p className="font-semibold" style={{ color: 'var(--wb-text)' }}>
            自动标注监控
          </p>
          <p className="text-sm wb-text-muted mt-1">看系统背后自动做了什么</p>
        </button>
        <button
          type="button"
          onClick={() => navigate('/runtime/prompt')}
          className="wb-card p-5 text-left border-2 border-transparent hover:border-[var(--wb-amber)] min-h-[100px]"
        >
          <ClipboardCheck className="w-6 h-6 mb-2" style={{ color: 'var(--wb-amber)' }} />
          <p className="font-semibold" style={{ color: 'var(--wb-text)' }}>
            提示标注工作区
          </p>
          <p className="text-sm wb-text-muted mt-1">中等置信度 · 人工确认强化学习</p>
        </button>
      </div>

      <button
        type="button"
        onClick={() => setExpandMetrics((v) => !v)}
        className="flex items-center gap-2 text-sm wb-text-secondary mb-2 min-h-[44px]"
      >
        {expandMetrics ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        企业风险与图谱详情（可选展开）
      </button>

      {expandMetrics && (
        <div className="wb-card p-4 space-y-4">
          {risk?.overall_risk_level && (
            <div className="flex items-center gap-2 text-sm">
              <AlertTriangle className="w-4 h-4" style={{ color: 'var(--wb-amber)' }} />
              <span className="wb-text-secondary">
                整体风险等级：<strong>{risk.overall_risk_level}</strong>
                {risk.top_risk?.score_pct != null && ` · 顶部域 ${risk.top_risk.score_pct}%`}
              </span>
            </div>
          )}
          {metrics && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs wb-text-muted">
              <span>活跃关系：{metrics.active_count ?? '—'}</span>
              <span>节点：{metrics.total_nodes ?? '—'}</span>
              <span>待审核：{metrics.pending_review_count ?? '—'}</span>
              <span>关系总数：{metrics.total_relations ?? '—'}</span>
            </div>
          )}
          {!risk && !metrics && <p className="text-sm wb-text-muted">暂无后端数据</p>}
        </div>
      )}
    </div>
  )
}
