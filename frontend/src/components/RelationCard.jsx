/**
 * RelationCard — HITL 待审核关系卡片
 */
import { useState } from 'react'
import { CheckCircle, XCircle, ExternalLink, FileText } from 'lucide-react'
import ConfidenceBar from './ConfidenceBar'

const PROVENANCE_LABELS = {
  llm_extracted: 'AI 抽取',
  manual_engineer: '工程师录入',
  mes_structured: 'MES 结构化数据',
  sensor_realtime: '传感器实时',
  sensor_historical: '传感器历史',
}

export default function RelationCard({ relation, onApprove, onReject }) {
  const [showSource, setShowSource] = useState(false)
  const [status, setStatus] = useState('pending') // 'pending' | 'approved' | 'rejected'

  const handleApprove = () => {
    setStatus('approved')
    onApprove?.(relation.id)
  }

  const handleReject = () => {
    setStatus('rejected')
    onReject?.(relation.id)
  }

  if (status !== 'pending') {
    return (
      <div className={`rounded-xl border px-6 py-4 flex items-center gap-3 ${
        status === 'approved'
          ? 'border-green-800 bg-green-900/20'
          : 'border-red-800 bg-red-900/20'
      }`}>
        {status === 'approved'
          ? <CheckCircle className="w-5 h-5 text-confidence-high" />
          : <XCircle className="w-5 h-5 text-confidence-low" />
        }
        <div>
          <p className="font-mono text-sm text-gray-300">{relation.relation_type}</p>
          <p className="text-xs text-gray-500">
            {status === 'approved' ? '已确认录入知识图谱' : '已否定，置信度将调低'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-surface rounded-xl border border-gray-700">
      {/* 关系类型标头 */}
      <div className="px-5 py-4 border-b border-gray-700">
        <code className="text-sm text-blue-400 font-mono">{relation.relation_type}</code>
        <div className="mt-1.5 text-base font-semibold text-white">
          {relation.source_node_id}
          <span className="text-gray-500 mx-2">→</span>
          {relation.target_node_id}
        </div>
      </div>

      {/* 置信度 + 来源信息 */}
      <div className="px-5 py-4 space-y-3">
        <ConfidenceBar value={relation.confidence} size="sm" />

        <div className="flex flex-wrap gap-3 text-xs text-gray-500">
          <span className="bg-bg px-2.5 py-1 rounded-full border border-gray-800">
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
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              <FileText className="w-3.5 h-3.5" />
              {showSource ? '隐藏原始文本' : '查看原始文本'}
              <ExternalLink className="w-3 h-3" />
            </button>
            {showSource && (
              <p className="mt-2 text-xs text-gray-400 bg-bg rounded-lg p-3 border border-gray-800 leading-relaxed italic">
                "{relation.source_text}"
              </p>
            )}
          </div>
        )}
      </div>

      {/* 操作按钮 */}
      <div className="px-5 pb-5 grid grid-cols-2 gap-3">
        <button
          onClick={handleApprove}
          className="flex items-center justify-center gap-2 py-2.5 rounded-lg bg-confidence-high hover:bg-green-500 transition-colors font-medium text-white text-sm"
        >
          <CheckCircle className="w-4 h-4" />
          确认
        </button>
        <button
          onClick={handleReject}
          className="flex items-center justify-center gap-2 py-2.5 rounded-lg bg-confidence-low hover:bg-red-500 transition-colors font-medium text-white text-sm"
        >
          <XCircle className="w-4 h-4" />
          否定
        </button>
      </div>
    </div>
  )
}
