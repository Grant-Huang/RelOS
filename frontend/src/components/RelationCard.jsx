/**
 * RelationCard — HITL 待审核关系卡片
 */
import { useState } from 'react'
import { CheckCircle, XCircle, ExternalLink, FileText, HelpCircle } from 'lucide-react'
import ConfidenceBar from './ConfidenceBar'

const PROVENANCE_LABELS = {
  llm_extracted: 'AI 抽取',
  manual_engineer: '工程师录入',
  mes_structured: 'MES 结构化数据',
  sensor_realtime: '传感器实时',
  sensor_historical: '传感器历史',
}

export default function RelationCard({ relation, onApprove, onReject, onUnsure }) {
  const [showSource, setShowSource] = useState(false)
  const [status, setStatus] = useState('pending') // 'pending' | 'approved' | 'rejected' | 'unsure'

  const handleApprove = () => {
    setStatus('approved')
    onApprove?.(relation.id)
  }

  const handleReject = () => {
    setStatus('rejected')
    onReject?.(relation.id)
  }

  const handleUnsure = () => {
    setStatus('unsure')
    onUnsure?.(relation.id)
  }

  if (status !== 'pending') {
    const unsure = status === 'unsure'
    return (
      <div
        className={`rounded-xl border px-6 py-4 flex items-center gap-3 ${
          status === 'approved'
            ? 'border-green-800 bg-green-900/20'
            : unsure
              ? 'wb-card'
              : 'border-red-800 bg-red-900/20'
        }`}
        style={
          unsure
            ? { borderColor: 'var(--wb-border)', background: 'var(--wb-surface-2)' }
            : undefined
        }
      >
        {status === 'approved' ? (
          <CheckCircle className="w-5 h-5 text-confidence-high" />
        ) : unsure ? (
          <HelpCircle className="w-5 h-5" style={{ color: 'var(--wb-amber)' }} />
        ) : (
          <XCircle className="w-5 h-5 text-confidence-low" />
        )}
        <div>
          <p className="font-mono text-sm wb-text-secondary">{relation.relation_type}</p>
          <p className="text-xs wb-text-muted">
            {status === 'approved'
              ? '已确认录入知识图谱'
              : unsure
                ? '已跳过（未调用接口）；可稍后从全量队列再处理'
                : '已否定，置信度将调低'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="wb-card rounded-xl">
      {/* 关系类型标头 */}
      <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--wb-border)' }}>
        <code className="text-sm font-mono" style={{ color: 'var(--wb-blue)' }}>
          {relation.relation_type}
        </code>
        <div className="mt-1.5 text-base font-semibold" style={{ color: 'var(--wb-text)' }}>
          {relation.source_node_id}
          <span className="wb-text-muted mx-2">→</span>
          {relation.target_node_id}
        </div>
      </div>

      {/* 置信度 + 来源信息 */}
      <div className="px-5 py-4 space-y-3">
        <ConfidenceBar value={relation.confidence} size="sm" />

        <div className="flex flex-wrap gap-3 text-xs wb-text-muted">
          <span className="px-2.5 py-1 rounded-full border" style={{ background: 'var(--wb-surface-2)', borderColor: 'var(--wb-border)' }}>
            {PROVENANCE_LABELS[relation.provenance] || relation.provenance}
          </span>
          {relation.created_at && (
            <span>{new Date(relation.created_at).toLocaleDateString('zh-CN')}</span>
          )}
        </div>

        {/* 来源文本（可展开） */}
        {relation.source_text && (
          <div>
            <button
              onClick={() => setShowSource(!showSource)}
              className="flex items-center gap-1.5 text-xs wb-text-muted hover:opacity-80 transition-opacity"
            >
              <FileText className="w-3.5 h-3.5" />
              {showSource ? '隐藏原始文本' : '查看原始文本'}
              <ExternalLink className="w-3 h-3" />
            </button>
            {showSource && (
              <p
                className="mt-2 text-xs rounded-lg p-3 border leading-relaxed italic wb-text-secondary"
                style={{ background: 'var(--wb-surface-2)', borderColor: 'var(--wb-border)' }}
              >
                "{relation.source_text}"
              </p>
            )}
          </div>
        )}
      </div>

      {/* 操作按钮 */}
      <div className={`px-5 pb-5 grid gap-3 ${onUnsure ? 'grid-cols-1 sm:grid-cols-3' : 'grid-cols-2'}`}>
        <button
          type="button"
          onClick={handleApprove}
          className="flex items-center justify-center gap-2 py-3 rounded-lg wb-btn-success font-medium text-sm min-h-[44px]"
        >
          <CheckCircle className="w-4 h-4" />
          确认
        </button>
        <button
          type="button"
          onClick={handleReject}
          className="flex items-center justify-center gap-2 py-3 rounded-lg wb-btn-danger font-medium text-sm min-h-[44px]"
        >
          <XCircle className="w-4 h-4" />
          否定
        </button>
        {onUnsure && (
          <button
            type="button"
            onClick={handleUnsure}
            className="flex items-center justify-center gap-2 py-3 rounded-lg wb-btn-ghost font-medium text-sm min-h-[44px]"
          >
            <HelpCircle className="w-4 h-4" />
            不确定
          </button>
        )}
      </div>
    </div>
  )
}
