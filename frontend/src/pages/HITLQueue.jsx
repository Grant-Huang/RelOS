/**
 * HITLQueue — 待审核关系队列（Human-in-the-Loop）
 * LLM 抽取的关系必须经人工确认才能进入知识图谱
 */
import { useEffect, useState } from 'react'
import { ClipboardCheck, Filter, RefreshCw, CheckCircle, AlertTriangle } from 'lucide-react'
import RelationCard from '../components/RelationCard'
import { listRelations, approveRelation, rejectRelation } from '../api/client'

// 演示用 mock 数据（当后端不可用时降级展示）
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

const SORT_OPTIONS = [
  { value: 'confidence_asc', label: '置信度从低到高' },
  { value: 'confidence_desc', label: '置信度从高到低' },
  { value: 'time_desc', label: '最新优先' },
]

export default function HITLQueue() {
  const [relations, setRelations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [useMock, setUseMock] = useState(false)
  const [sortBy, setSortBy] = useState('confidence_asc')
  const [approved, setApproved] = useState(new Set())
  const [rejected, setRejected] = useState(new Set())

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listRelations({ status: 'pending_review', limit: 50 })
      const items = Array.isArray(data) ? data : (data?.items || data?.relations || [])
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

  useEffect(() => { load() }, [])

  const sortedRelations = [...relations].sort((a, b) => {
    if (sortBy === 'confidence_asc') return a.confidence - b.confidence
    if (sortBy === 'confidence_desc') return b.confidence - a.confidence
    return new Date(b.created_at || 0) - new Date(a.created_at || 0)
  })

  const pending = sortedRelations.filter(r => !approved.has(r.id) && !rejected.has(r.id))
  const doneCount = approved.size + rejected.size

  const handleApprove = async (id) => {
    try {
      if (!useMock) await approveRelation(id)
    } catch { /* 静默处理 */ }
    setApproved(prev => new Set([...prev, id]))
  }

  const handleReject = async (id) => {
    try {
      if (!useMock) await rejectRelation(id)
    } catch { /* 静默处理 */ }
    setRejected(prev => new Set([...prev, id]))
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      {/* 页头 */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <ClipboardCheck className="w-6 h-6 text-yellow-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">待审核关系</h1>
            <p className="text-gray-500 text-sm">Human-in-the-Loop · LLM 抽取关系需人工确认</p>
          </div>
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

      {/* 演示数据提示 */}
      {useMock && (
        <div className="mb-6 bg-blue-900/30 border border-blue-800 rounded-xl px-5 py-3 flex items-center gap-3">
          <AlertTriangle className="w-4 h-4 text-blue-400 flex-shrink-0" />
          <p className="text-sm text-blue-300">
            使用演示数据（后端未返回待审核关系）
          </p>
        </div>
      )}

      {/* 统计 + 筛选栏 */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-yellow-400"></span>
            <span className="text-sm text-gray-400">待审核 <strong className="text-white">{pending.length}</strong> 条</span>
          </div>
          {doneCount > 0 && (
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-green-400" />
              <span className="text-sm text-gray-400">已处理 <strong className="text-white">{doneCount}</strong> 条</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-500" />
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-surface border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-blue-600"
          >
            {SORT_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* 关系列表 */}
      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-surface rounded-xl border border-gray-700 h-40 animate-pulse" />
          ))}
        </div>
      ) : pending.length > 0 ? (
        <div className="space-y-4">
          {pending.map(rel => (
            <RelationCard
              key={rel.id}
              relation={rel}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-16">
          <CheckCircle className="w-12 h-12 text-confidence-high mx-auto mb-4" />
          <p className="text-lg font-semibold text-white">全部审核完成</p>
          <p className="text-gray-500 text-sm mt-1">
            已处理 {doneCount} 条关系（{approved.size} 确认，{rejected.size} 否定）
          </p>
        </div>
      )}
    </div>
  )
}
