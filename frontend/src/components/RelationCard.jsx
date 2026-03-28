/**
 * RelationCard — HITL 待审核关系（仅用全局 relos 设计令牌：.card / .btn / .muted / .rrow）
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
  const [status, setStatus] = useState('pending')

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
        className="card"
        style={{
          borderColor: status === 'approved' ? 'var(--tone-ok-border)' : unsure ? 'var(--b1)' : 'var(--tone-bad-border)',
          background: status === 'approved' ? 'var(--tone-ok-bg)' : unsure ? 'var(--bg2)' : 'var(--tone-bad-bg)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {status === 'approved' ? (
            <CheckCircle style={{ width: 22, height: 22, flexShrink: 0, color: 'var(--green)' }} />
          ) : unsure ? (
            <HelpCircle style={{ width: 22, height: 22, flexShrink: 0, color: 'var(--amber)' }} />
          ) : (
            <XCircle style={{ width: 22, height: 22, flexShrink: 0, color: 'var(--red)' }} />
          )}
          <div>
            <p style={{ fontFamily: 'ui-monospace, monospace', fontSize: 12, color: 'var(--t1)', margin: 0 }}>{relation.relation_type}</p>
            <p className="muted" style={{ margin: '4px 0 0' }}>
              {status === 'approved'
                ? '已确认录入知识图谱'
                : unsure
                  ? '已跳过（未调用接口）；可稍后从全量队列再处理'
                  : '已否定，置信度将调低'}
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: '14px 16px', borderBottom: '0.5px solid var(--b1)' }}>
        <code style={{ fontSize: 12, fontFamily: 'ui-monospace, monospace', color: 'var(--blue-ink)' }}>{relation.relation_type}</code>
        <div style={{ marginTop: 8, fontSize: 15, fontWeight: 600, color: 'var(--t1)' }}>
          {relation.source_node_id}
          <span className="muted" style={{ margin: '0 8px' }}>
            →
          </span>
          {relation.target_node_id}
        </div>
      </div>

      <div style={{ padding: '14px 16px' }}>
        <ConfidenceBar value={relation.confidence} size="sm" />

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
          <span className="rnode" style={{ fontSize: 11 }}>
            {PROVENANCE_LABELS[relation.provenance] || relation.provenance}
          </span>
          {relation.created_at && <span className="muted">{new Date(relation.created_at).toLocaleDateString('zh-CN')}</span>}
        </div>

        {relation.source_text && (
          <div style={{ marginTop: 12 }}>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => setShowSource(!showSource)}
              style={{ border: 'none', padding: 0, background: 'none', color: 'var(--t2)' }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <FileText style={{ width: 14, height: 14 }} />
                {showSource ? '隐藏原始文本' : '查看原始文本'}
                <ExternalLink style={{ width: 12, height: 12 }} />
              </span>
            </button>
            {showSource && (
              <p
                className="ann-src"
                style={{ marginTop: 10, marginBottom: 0, fontStyle: 'italic', color: 'var(--t2)' }}
              >
                &quot;{relation.source_text}&quot;
              </p>
            )}
          </div>
        )}
      </div>

      <div
        style={{
          padding: '0 16px 16px',
          display: 'grid',
          gap: 8,
          gridTemplateColumns: onUnsure ? 'repeat(3, minmax(0, 1fr))' : 'repeat(2, minmax(0, 1fr))',
        }}
      >
        <button type="button" className="btn btn-ok btn-sm" onClick={handleApprove} style={{ justifyContent: 'center', minHeight: 44 }}>
          <CheckCircle style={{ width: 16, height: 16 }} />
          确认
        </button>
        <button type="button" className="btn btn-no btn-sm" onClick={handleReject} style={{ justifyContent: 'center', minHeight: 44 }}>
          <XCircle style={{ width: 16, height: 16 }} />
          否定
        </button>
        {onUnsure && (
          <button type="button" className="btn btn-sm" onClick={handleUnsure} style={{ justifyContent: 'center', minHeight: 44 }}>
            <HelpCircle style={{ width: 16, height: 16 }} />
            不确定
          </button>
        )}
      </div>
    </div>
  )
}
