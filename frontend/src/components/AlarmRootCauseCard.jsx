/**
 * 告警根因卡片：样式对齐 workbench v2（.card / .btn / .badge / .rrow / .muted）
 */
import { useState } from 'react'
import { ChevronDown, ChevronUp, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import ConfidenceBar from './ConfidenceBar'

const ENGINE_LABELS = {
  rule_engine: '规则引擎',
  llm: 'AI 分析',
  hitl: '人工审核',
}

export default function AlarmRootCauseCard({
  alarmCode,
  deviceName,
  recommendedCause,
  confidence,
  engineUsed = 'rule_engine',
  shadowMode = true,
  supportingRelations = [],
  onConfirm,
  onReject,
  loading = false,
}) {
  const [expanded, setExpanded] = useState(false)
  const [feedback, setFeedback] = useState(null)

  const handleConfirm = () => {
    setFeedback('confirmed')
    onConfirm?.()
  }

  const handleReject = () => {
    setFeedback('rejected')
    onReject?.()
  }

  if (feedback) {
    return (
      <div className="card">
        <div style={{ textAlign: 'center', padding: '16px 8px' }}>
          {feedback === 'confirmed' ? (
            <>
              <CheckCircle className="mx-auto mb-2" style={{ width: 40, height: 40, color: 'var(--green)' }} />
              <p style={{ fontWeight: 600, fontSize: 15, color: 'var(--green)', marginBottom: 8 }}>反馈已提交</p>
              <p className="muted" style={{ fontSize: 12 }}>
                系统已学习这条经验，置信度将随反馈持续优化
              </p>
            </>
          ) : (
            <>
              <XCircle className="mx-auto mb-2" style={{ width: 40, height: 40, color: 'var(--red)' }} />
              <p style={{ fontWeight: 600, fontSize: 15, color: 'var(--red)', marginBottom: 8 }}>已标记为不适用</p>
              <p className="muted" style={{ fontSize: 12 }}>
                感谢反馈，系统将调低此推荐的置信度
              </p>
            </>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div
        style={{
          padding: '14px 16px',
          borderBottom: '0.5px solid var(--b1)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <div>
          <p style={{ fontWeight: 600, fontSize: 13, color: 'var(--t1)' }}>{deviceName}</p>
          <p className="muted" style={{ fontFamily: 'ui-monospace, monospace', marginTop: 2 }}>
            {alarmCode}
          </p>
        </div>
        <span className="badge b-red" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <AlertTriangle style={{ width: 12, height: 12 }} />
          告警触发
        </span>
      </div>

      <div style={{ padding: '16px 18px' }}>
        <div className="q-num">推荐根因</div>
        <div className="q-text" style={{ fontWeight: 600, fontSize: 16, marginBottom: 12 }}>
          {recommendedCause}
        </div>
        <ConfidenceBar value={confidence} size="md" />

        <div style={{ marginTop: 12, fontSize: 12, color: 'var(--t2)' }}>
          引擎：
          <span style={{ fontWeight: 500, color: 'var(--blue)' }}>
            {ENGINE_LABELS[engineUsed] || engineUsed}
          </span>
        </div>
      </div>

      {supportingRelations.length > 0 && (
        <div style={{ borderTop: '0.5px solid var(--b1)' }}>
          <button type="button" className="btn-row-expand" onClick={() => setExpanded(!expanded)}>
            <span>查看依据关系（{supportingRelations.length} 条）</span>
            {expanded ? <ChevronUp style={{ width: 16, height: 16 }} /> : <ChevronDown style={{ width: 16, height: 16 }} />}
          </button>

          {expanded && (
            <div style={{ padding: '0 16px 14px' }}>
              {supportingRelations.map((rel, i) => (
                <div key={i} className="rrow" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 8 }}>
                  <p style={{ fontFamily: 'ui-monospace, monospace', fontSize: 11, color: 'var(--blue)' }}>
                    {rel.relation_type}
                  </p>
                  <p style={{ fontSize: 12, color: 'var(--t1)' }}>
                    {rel.source_node_id} → {rel.target_node_id}
                  </p>
                  {rel.notes && <p className="muted" style={{ fontSize: 11, fontStyle: 'italic' }}>&quot;{rel.notes}&quot;</p>}
                  <ConfidenceBar value={rel.confidence} size="sm" />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {shadowMode && (
        <div
          className="ann-src"
          style={{
            margin: '0 16px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            border: '0.5px solid var(--b1)',
          }}
        >
          <AlertTriangle style={{ width: 16, height: 16, flexShrink: 0, color: 'var(--amber)' }} />
          <p style={{ fontSize: 12, color: 'var(--t2)', margin: 0 }}>Shadow Mode 开启 · 建议已记录，未自动下发工单</p>
        </div>
      )}

      <div className="ann-actions" style={{ padding: '0 16px 16px', marginTop: 0 }}>
        <button type="button" className="btn btn-ok flex-1 justify-center" disabled={loading} onClick={handleConfirm}>
          <CheckCircle style={{ width: 16, height: 16 }} />
          确认根因
        </button>
        <button type="button" className="btn btn-no flex-1 justify-center" disabled={loading} onClick={handleReject}>
          <XCircle style={{ width: 16, height: 16 }} />
          不是这个
        </button>
      </div>
    </div>
  )
}
