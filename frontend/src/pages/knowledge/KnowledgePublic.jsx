/**
 * 公开知识标注 — 对齐 docs/relos_workbench_v2.html #v-kb-public
 * 预标注与示例文本来自后端（data/demo + /knowledge/public/extract）
 */
import { useState, useEffect } from 'react'
import { createRelation, extractPublicKnowledge, getTextSamplesConfig } from '../../api/client'

const REL_TYPES = ['INDICATES', 'CAUSES', 'AFFECTS', 'BLOCKS', 'PRODUCES', 'DEPENDS_ON', 'OPERATES', 'DEPLETES']

export default function KnowledgePublic() {
  const [text, setText] = useState('')
  const [sourceType, setSourceType] = useState('ISO 标准')
  const [selRelType, setSelRelType] = useState('INDICATES')
  const [previewHtml, setPreviewHtml] = useState('')
  const [drafts, setDrafts] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [msg, setMsg] = useState(null)
  const [textSamples, setTextSamples] = useState({})

  useEffect(() => {
    let cancelled = false
    getTextSamplesConfig()
      .then((s) => {
        if (!cancelled) setTextSamples(s && typeof s === 'object' ? s : {})
      })
      .catch(() => {
        if (!cancelled) setTextSamples({})
      })
    return () => {
      cancelled = true
    }
  }, [])

  const loadSample = (k) => {
    setText(textSamples[k] || '')
    setMsg(null)
  }

  const autoExtract = async () => {
    if (!text.trim()) {
      setMsg({ type: 'err', text: '请先输入或粘贴文本' })
      return
    }
    setExtracting(true)
    setMsg(null)
    try {
      const res = await extractPublicKnowledge({ text: text.trim(), source_label: sourceType })
      const data = res?.data ?? res
      setPreviewHtml(data.preview_html || '')
      setDrafts(Array.isArray(data.drafts) ? data.drafts : [])
      if (!data.drafts?.length) {
        setMsg({ type: 'info', text: '未抽取到候选关系，可尝试更长文本或检查后端日志。' })
      } else {
        setMsg({ type: 'info', text: 'AI 预标注完成，请审核下方候选关系。' })
      }
    } catch (e) {
      setPreviewHtml('')
      setDrafts([])
      setMsg({ type: 'err', text: e.message || '抽取失败，请确认后端已启动。' })
    } finally {
      setExtracting(false)
    }
  }

  const clearPub = () => {
    setText('')
    setPreviewHtml('')
    setDrafts([])
    setMsg(null)
  }

  const commitPublic = async () => {
    if (drafts.length === 0) {
      setMsg({ type: 'err', text: '请先执行 AI 预标注。' })
      return
    }
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
          provenance_detail: `${sourceType} · ${text.slice(0, 200)}`,
          status: 'pending_review',
        })
      }
      setDrafts([])
      setText('')
      setPreviewHtml('')
      setMsg({ type: 'ok', text: '已提交至 RelOS 公开知识层（pending_review）。' })
    } catch (e) {
      setMsg({ type: 'err', text: e.message || '提交失败' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="relos-page">
      <h2>
        公开知识标注 <span className="layer-pill lp1">知识层 1 · Public Knowledge</span>
      </h2>
      <div className="muted mb12">从行业标准、学术文献、公开手册中抽取关系知识，构建领域通用本体基础层。</div>

      <div className="g2 mb12">
        <div className="card">
          <h3>输入文本片段</h3>
          <div style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
              <button type="button" className="btn btn-sm" onClick={() => loadSample('bearing')}>
                示例：轴承故障
              </button>
              <button type="button" className="btn btn-sm" onClick={() => loadSample('quality')}>
                示例：质量管控
              </button>
              <button type="button" className="btn btn-sm" onClick={() => loadSample('oee')}>
                示例：OEE分析
              </button>
            </div>
            <textarea rows={7} value={text} onChange={(e) => setText(e.target.value)} placeholder="粘贴或输入行业文献、标准手册文本..." />
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <select value={sourceType} onChange={(e) => setSourceType(e.target.value)} style={{ flex: 1, minWidth: 140 }}>
              <option>ISO 标准</option>
              <option>行业白皮书</option>
              <option>学术论文</option>
              <option>设备手册</option>
            </select>
            <button type="button" className="btn btn-p" onClick={autoExtract} disabled={extracting}>
              {extracting ? '抽取中…' : 'AI 预标注'}
            </button>
          </div>
        </div>

        <div className="card">
          <h3>实体类型 · 颜色图例</h3>
          <div style={{ marginBottom: 10, display: 'flex', flexDirection: 'column', gap: 5, fontSize: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="ent-span ent-machine">Machine / 设备</span>
              <span className="muted">物理设备实体</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="ent-span ent-alarm">Alarm / 报警</span>
              <span className="muted">故障信号类型</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="ent-span ent-issue">Issue / 问题</span>
              <span className="muted">根因/问题类型</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="ent-span ent-wo">WorkOrder / 工单</span>
              <span className="muted">生产工单</span>
            </div>
          </div>
          <div className="div" />
          <h3>关系类型选择</h3>
          <div id="rel-chips" style={{ marginTop: 6 }}>
            {REL_TYPES.map((r) => (
              <span
                key={r}
                role="button"
                tabIndex={0}
                className={`chip${selRelType === r ? ' on' : ''}`}
                onClick={() => setSelRelType(r)}
                onKeyDown={(e) => e.key === 'Enter' && setSelRelType(r)}
              >
                {r}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <h3 style={{ marginBottom: 0 }}>标注预览 & 提取关系</h3>
          <div style={{ display: 'flex', gap: 6 }}>
            <button type="button" className="btn btn-sm btn-ok" disabled={submitting} onClick={commitPublic}>
              提交到图谱
            </button>
            <button type="button" className="btn btn-sm" onClick={clearPub}>
              清除
            </button>
          </div>
        </div>
        {previewHtml ? (
          <div
            id="pub-preview"
            className="doc-chunk"
            style={{ minHeight: 60, color: 'var(--t2)' }}
            dangerouslySetInnerHTML={{ __html: previewHtml }}
          />
        ) : (
          <div id="pub-preview" className="doc-chunk" style={{ minHeight: 60, color: 'var(--t2)' }}>
            点击「AI 预标注」后在此预览实体和关系...
          </div>
        )}
        <div id="pub-rels" className="mt8">
          {drafts.length > 0 ? (
            <>
              <h3 style={{ marginBottom: 7 }}>AI 提取候选关系（请审核）</h3>
              {drafts.map((d) => (
                <div key={d.clientKey} className="rel-pending">
                  <span className="rnode">{d.short?.[0] ?? d.source_node_id}</span>
                  <span style={{ fontSize: 10, color: 'var(--t2)' }}>→ {d.short?.[1] ?? '—'} →</span>
                  <span className="rnode">{d.short?.[2] ?? d.target_node_id}</span>
                  <div style={{ flex: 1 }} />
                  <span className="badge b-amber">{d.short?.[3] ?? Number(d.confidence).toFixed(2)}</span>
                  <button type="button" className="btn btn-ok btn-sm" onClick={() => setMsg({ type: 'info', text: '单条写入请使用底部「提交到图谱」批量提交。' })}>
                    ✓
                  </button>
                  <button type="button" className="btn btn-no btn-sm" onClick={() => setDrafts((prev) => prev.filter((x) => x.clientKey !== d.clientKey))}>
                    ✗
                  </button>
                </div>
              ))}
            </>
          ) : null}
        </div>
      </div>

      {msg && (
        <p
          className="muted mt8"
          style={{
            padding: '8px 10px',
            borderRadius: 8,
            background: msg.type === 'ok' ? 'var(--green-l)' : msg.type === 'err' ? 'var(--red-l)' : 'var(--bg2)',
            color: msg.type === 'ok' ? 'var(--green)' : msg.type === 'err' ? 'var(--red)' : 'var(--t2)',
          }}
        >
          {msg.text}
        </p>
      )}
    </div>
  )
}
