/**
 * 提示标注工作区：置信度 0.50–0.79 · POST /relations/{id}/feedback
 */
import { useEffect, useState } from 'react'
import { ClipboardCheck, RefreshCw, Filter, AlertTriangle, CheckCircle } from 'lucide-react'
import RelationCard from '../../components/RelationCard'
import { listPendingRelations, submitRelationFeedback } from '../../api/client'

const MOCK_RELATIONS = [
  {
    id: 'rel-mock-1',
    relation_type: 'ALARM__INDICATES__COMPONENT_FAILURE',
    source_node_id: 'alarm-VIB-001',
    target_node_id: '轴承磨损',
    confidence: 0.58,
    provenance: 'llm_extracted',
    status: 'pending_review',
    source_text: '2024年12月维修记录：1号机振动报警，经检查发现主轴轴承磨损严重，更换后恢复正常。',
    created_at: '2024-12-15T10:30:00Z',
  },
  {
    id: 'rel-mock-2',
    relation_type: 'ALARM__INDICATES__COMPONENT_FAILURE',
    source_node_id: 'alarm-TEMP-002',
    target_node_id: '电机绕组过热',
    confidence: 0.62,
    provenance: 'llm_extracted',
    status: 'pending_review',
    source_text: '设备维保手册第7章：温度告警通常与电机绕组绝缘老化或冷却系统失效相关。',
    created_at: '2025-01-10T08:15:00Z',
  },
  {
    id: 'rel-mock-3',
    relation_type: 'DEVICE__TRIGGERS__ALARM',
    source_node_id: 'device-M3',
    target_node_id: 'alarm-WELD-003',
    confidence: 0.71,
    provenance: 'llm_extracted',
    status: 'pending_review',
    source_text: 'M3焊接机近半年告警记录分析：过热告警占比67%，主要集中在夜班操作期间。',
    created_at: '2025-02-20T14:00:00Z',
  },
]

const ENGINEER_KEY = 'relos_engineer_id'

function inPromptRange(c) {
  return c >= 0.5 && c <= 0.79
}

export default function PromptLabeling() {
  const [relations, setRelations] = useState([])
  const [loading, setLoading] = useState(true)
  const [useMock, setUseMock] = useState(false)
  const [filterMode, setFilterMode] = useState('prompt')
  const [sortBy, setSortBy] = useState('confidence_asc')
  const [processed, setProcessed] = useState(new Set())
  const [engineerId, setEngineerId] = useState(() => {
    try {
      return localStorage.getItem(ENGINEER_KEY) || 'operator-1'
    } catch {
      return 'operator-1'
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(ENGINEER_KEY, engineerId)
    } catch {
      /* ignore */
    }
  }, [engineerId])

  const load = async () => {
    setLoading(true)
    try {
      const data = await listPendingRelations(80)
      const items = Array.isArray(data) ? data : []
      if (items.length === 0) {
        setRelations(MOCK_RELATIONS)
        setUseMock(true)
      } else {
        setRelations(items)
        setUseMock(false)
      }
    } catch {
      setRelations(MOCK_RELATIONS)
      setUseMock(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const sorted = [...relations].sort((a, b) => {
    if (sortBy === 'confidence_asc') return a.confidence - b.confidence
    if (sortBy === 'confidence_desc') return b.confidence - a.confidence
    return new Date(b.created_at || 0) - new Date(a.created_at || 0)
  })

  const visible = sorted.filter((r) => {
    if (processed.has(r.id)) return false
    if (filterMode === 'prompt') return inPromptRange(Number(r.confidence))
    return true
  })

  const outOfRange = sorted.filter((r) => !inPromptRange(Number(r.confidence)) && !processed.has(r.id))

  const doFeedback = async (id, confirmed) => {
    if (!useMock) {
      try {
        await submitRelationFeedback(id, { engineer_id: engineerId, confirmed })
      } catch {
        /* 仍标记本地已处理，避免卡住 */
      }
    }
    setProcessed((prev) => new Set([...prev, id]))
  }

  const handleUnsure = (id) => {
    setProcessed((prev) => new Set([...prev, id]))
  }

  return (
    <div className="p-4 md:p-8 max-w-3xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div className="flex items-center gap-3">
          <ClipboardCheck className="w-6 h-6" style={{ color: 'var(--wb-amber)' }} />
          <div>
            <h1 className="text-xl md:text-2xl font-semibold" style={{ color: 'var(--wb-text)' }}>
              提示标注工作区
            </h1>
            <p className="text-sm wb-text-muted">置信度 0.50–0.79 · 每次确认触发 Relation Core 更新</p>
          </div>
        </div>
        <button type="button" onClick={load} disabled={loading} className="wb-btn-ghost flex items-center gap-2 self-start min-h-[44px]">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      <div className="wb-card p-4 mb-5 space-y-3">
        <label className="block text-xs wb-text-muted">操作员工号（用于反馈审计）</label>
        <input
          className="wb-input max-w-xs min-h-[44px]"
          value={engineerId}
          onChange={(e) => setEngineerId(e.target.value)}
          placeholder="operator-1"
        />
      </div>

      {useMock && (
        <div className="mb-5 wb-card p-3 flex items-center gap-2" style={{ borderColor: 'var(--wb-blue)' }}>
          <AlertTriangle className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--wb-blue)' }} />
          <p className="text-sm wb-text-secondary">演示数据（后端无待审核关系或请求失败）</p>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 wb-text-muted" />
          <select
            value={filterMode}
            onChange={(e) => setFilterMode(e.target.value)}
            className="wb-select w-auto min-h-[44px] text-sm"
          >
            <option value="prompt">仅提示区（0.50–0.79）</option>
            <option value="all">全部待审核（高级）</option>
          </select>
        </div>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="wb-select w-auto min-h-[44px] text-sm"
        >
          <option value="confidence_asc">置信度从低到高</option>
          <option value="confidence_desc">置信度从高到低</option>
          <option value="time_desc">最新优先</option>
        </select>
        <span className="text-sm wb-text-muted">
          队列中 <strong style={{ color: 'var(--wb-text)' }}>{visible.length}</strong> 条
        </span>
      </div>

      {filterMode === 'prompt' && outOfRange.length > 0 && (
        <p className="text-xs wb-text-muted mb-4">
          另有 {outOfRange.length} 条置信度不在提示区，切换「全部待审核」可处理。
        </p>
      )}

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="wb-card h-36 animate-pulse" />
          ))}
        </div>
      ) : visible.length > 0 ? (
        <div className="space-y-4">
          {visible.map((rel) => (
            <RelationCard
              key={rel.id}
              relation={rel}
              onApprove={(id) => doFeedback(id, true)}
              onReject={(id) => doFeedback(id, false)}
              onUnsure={(id) => handleUnsure(id)}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-16 wb-card">
          <CheckCircle className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--wb-green)' }} />
          <p className="font-medium" style={{ color: 'var(--wb-text)' }}>
            提示区内暂无待处理项
          </p>
          <p className="text-sm wb-text-muted mt-1">可切换筛选或等待新任务</p>
        </div>
      )}
    </div>
  )
}
