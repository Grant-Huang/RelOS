/**
 * 公开知识（层 1）：粘贴 → AI 预标注占位 → 提交待审核
 */
import { useState } from 'react'
import { BookOpen, Sparkles, Send } from 'lucide-react'
import LayerAuthorityBar from '../../components/LayerAuthorityBar'
import { createRelation } from '../../api/client'

const MOCK_DRAFTS = [
  {
    clientKey: 'm1',
    relation_type: 'DEVICE__TRIGGERS__ALARM',
    source_node_id: 'device-line-a',
    source_node_type: 'Device',
    target_node_id: 'alarm-temp-high',
    target_node_type: 'Alarm',
    confidence: 0.72,
  },
  {
    clientKey: 'm2',
    relation_type: 'ALARM__INDICATES__COMPONENT_FAILURE',
    source_node_id: 'alarm-temp-high',
    source_node_type: 'Alarm',
    target_node_id: 'bearing-assembly',
    target_node_type: 'Component',
    confidence: 0.68,
  },
]

export default function KnowledgePublic() {
  const [text, setText] = useState('')
  const [drafts, setDrafts] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [msg, setMsg] = useState(null)

  const runMockAnnotate = () => {
    if (!text.trim()) {
      setMsg({ type: 'err', text: '请先粘贴一段公开知识摘要。' })
      return
    }
    setDrafts(MOCK_DRAFTS)
    setMsg({ type: 'info', text: '占位：已根据文本生成候选关系（演示数据），可提交至待审核。' })
  }

  const submitDrafts = async () => {
    if (drafts.length === 0) return
    setSubmitting(true)
    setMsg(null)
    try {
      for (const r of drafts) {
        await createRelation({
          relation_type: r.relation_type,
          source_node_id: r.source_node_id,
          source_node_type: r.source_node_type,
          target_node_id: r.target_node_id,
          target_node_type: r.target_node_type,
          confidence: r.confidence,
          provenance: 'llm_extracted',
          knowledge_phase: 'bootstrap',
          phase_weight: 0.35,
          half_life_days: 90,
          provenance_detail: text.slice(0, 200),
          status: 'pending_review',
        })
      }
      setDrafts([])
      setText('')
      setMsg({ type: 'ok', text: '已提交至图谱待审核队列（pending_review）。' })
    } catch (e) {
      setMsg({ type: 'err', text: e.message || '提交失败' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="wb-main p-4 md:p-8 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-4">
        <BookOpen className="w-7 h-7 flex-shrink-0" style={{ color: 'var(--wb-blue)' }} />
        <div>
          <h1 className="text-xl md:text-2xl font-semibold" style={{ color: 'var(--wb-text)' }}>
            公开知识标注
          </h1>
          <p className="text-sm wb-text-muted">层 1 · 行业标准与公开材料，预标注后需人工审核</p>
        </div>
      </div>

      <LayerAuthorityBar layer={1} />

      <div className="wb-card p-4 mb-4 space-y-3">
        <label className="text-xs font-semibold wb-text-muted uppercase tracking-wide">粘贴文本</label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="wb-input min-h-[160px] resize-y"
          placeholder="粘贴公开手册摘要、行业标准片段等…"
        />
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={runMockAnnotate}
            className="wb-btn-primary inline-flex items-center gap-2 min-h-[44px]"
          >
            <Sparkles className="w-4 h-4" />
            AI 预标注（占位）
          </button>
        </div>
      </div>

      {drafts.length > 0 && (
        <div className="wb-card p-4 mb-4">
          <h2 className="text-sm font-semibold wb-text-secondary mb-3">候选关系预览</h2>
          <ul className="space-y-2 text-sm wb-text-secondary mb-4">
            {drafts.map((d) => (
              <li key={d.clientKey} className="wb-card-muted p-3 rounded-lg font-mono text-xs">
                {d.relation_type} · {d.source_node_id} → {d.target_node_id} · conf {d.confidence}
              </li>
            ))}
          </ul>
          <button
            type="button"
            disabled={submitting}
            onClick={submitDrafts}
            className="wb-btn-success inline-flex items-center gap-2 min-h-[44px] disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
            {submitting ? '提交中…' : '提交到待审核'}
          </button>
        </div>
      )}

      {msg && (
        <p
          className={`text-sm rounded-lg px-3 py-2 ${
            msg.type === 'ok'
              ? 'bg-[color:var(--wb-green-soft)] text-[color:var(--wb-green)]'
              : msg.type === 'err'
                ? 'bg-[color:var(--wb-red-soft)] text-[color:var(--wb-red)]'
                : 'wb-card-muted wb-text-secondary'
          }`}
        >
          {msg.text}
        </p>
      )}
    </div>
  )
}
