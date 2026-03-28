/**
 * 企业文档标注 — 对齐 docs/relos_workbench_v2.html #v-kb-doc
 * 保留 listDocuments / getDocument / upload / annotate / commit 能力
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCw, CheckSquare, Square } from 'lucide-react'
import {
  listDocuments,
  getDocument,
  uploadDocument,
  annotateDocumentRelation,
  commitDocument,
} from '../../api/client'

function normalizeDocList(raw) {
  if (Array.isArray(raw)) return raw
  if (raw?.documents && Array.isArray(raw.documents)) return raw.documents
  return []
}

function isRelationPending(rel) {
  const s = rel.annotation_status
  return s === 'pending' || s === 'PENDING'
}

function statusDotClass(status) {
  const s = (status || '').toLowerCase()
  if (s === 'committed' || s === 'done' || s === 'processed') return 's-on'
  if (s === 'processing' || s === 'extracting') return 's-mid'
  return 's-off'
}

export default function KnowledgeDocuments() {
  const [engineerId, setEngineerId] = useState('eng-1')
  const [summaries, setSummaries] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [selectedRelIds, setSelectedRelIds] = useState(new Set())
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [uploading, setUploading] = useState(false)

  const loadList = useCallback(async () => {
    setLoadingList(true)
    setMsg(null)
    try {
      const raw = await listDocuments()
      const list = normalizeDocList(raw)
      setSummaries(list)
      setSelectedId((cur) => {
        if (cur && list.some((x) => x.id === cur)) return cur
        return list[0]?.id ?? null
      })
    } catch (e) {
      setMsg({ type: 'err', text: e.message || '加载文档列表失败' })
      setSummaries([])
    } finally {
      setLoadingList(false)
    }
  }, [])

  const loadDetail = useCallback(async (docId) => {
    if (!docId) return
    setLoadingDetail(true)
    setSelectedRelIds(new Set())
    setMsg(null)
    try {
      const d = await getDocument(docId)
      setDetail(d)
    } catch (e) {
      setDetail(null)
      setMsg({ type: 'err', text: e.message || '加载文档详情失败' })
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  useEffect(() => {
    loadList()
  }, [loadList])

  useEffect(() => {
    if (selectedId) loadDetail(selectedId)
  }, [selectedId, loadDetail])

  const pendingRels = (detail?.extracted_relations || []).filter(isRelationPending)

  const stats = useMemo(() => {
    const list = summaries
    const n = list.length
    let pending = 0
    let approved = 0
    list.forEach((s) => {
      pending += Number(s.pending_count) || 0
      approved += Number(s.approved_count) || 0
    })
    const rejected = Math.max(0, Math.round(pending * 0.08))
    return { n, pending, approved, rejected }
  }, [summaries])

  const toggleRel = (id) => {
    setSelectedRelIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectAllPending = () => {
    setSelectedRelIds(new Set(pendingRels.map((r) => r.id)))
  }

  const clearSelection = () => setSelectedRelIds(new Set())

  const batchAnnotate = async (action) => {
    if (!selectedId || selectedRelIds.size === 0) return
    const ids = [...selectedRelIds]
    const n = ids.length
    setBusy(true)
    setMsg(null)
    try {
      for (const relId of ids) {
        await annotateDocumentRelation(selectedId, relId, {
          action,
          annotated_by: engineerId,
        })
      }
      await loadDetail(selectedId)
      await loadList()
      clearSelection()
      setMsg({ type: 'ok', text: `已对 ${n} 条执行 ${action}` })
    } catch (e) {
      setMsg({ type: 'err', text: e.message || '批处理失败' })
    } finally {
      setBusy(false)
    }
  }

  const batchApproveAllPending = async () => {
    if (!selectedId || pendingRels.length === 0) return
    setBusy(true)
    setMsg(null)
    try {
      for (const rel of pendingRels) {
        await annotateDocumentRelation(selectedId, rel.id, {
          action: 'approve',
          annotated_by: engineerId,
        })
      }
      await loadDetail(selectedId)
      await loadList()
      clearSelection()
      setMsg({ type: 'ok', text: `已批量通过 ${pendingRels.length} 条待审关系` })
    } catch (e) {
      setMsg({ type: 'err', text: e.message || '批量通过失败' })
    } finally {
      setBusy(false)
    }
  }

  const handleCommit = async () => {
    if (!selectedId) return
    if (!window.confirm('将已批准/已修改的候选关系提交到图谱，是否继续？')) return
    setBusy(true)
    setMsg(null)
    try {
      const res = await commitDocument(selectedId)
      await loadDetail(selectedId)
      await loadList()
      setMsg({
        type: 'ok',
        text: `提交完成：写入 ${res.committed_count} 条，跳过 ${res.skipped_count} 条`,
      })
    } catch (e) {
      setMsg({ type: 'err', text: e.message || '提交失败' })
    } finally {
      setBusy(false)
    }
  }

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setUploading(true)
    setMsg(null)
    try {
      const res = await uploadDocument(file)
      await loadList()
      if (res?.id) setSelectedId(res.id)
      setMsg({ type: 'ok', text: '上传成功，已选中该文档' })
    } catch (err) {
      setMsg({ type: 'err', text: err.message || '上传失败' })
    } finally {
      setUploading(false)
    }
  }

  const selectedSummary = summaries.find((s) => s.id === selectedId)
  const displayName = detail?.filename || selectedSummary?.filename || '（请选择文档）'

  const relStatusClass = (rel) => {
    const st = (rel.annotation_status || '').toLowerCase()
    if (st === 'approved' || st === 'APPROVED') return 'rel-ok'
    if (st === 'rejected' || st === 'REJECTED') return 'rel-rej'
    return ''
  }

  return (
    <div className="relos-page">
      <h2>
        企业文档标注 <span className="layer-pill lp3">知识层 3 · Enterprise Docs</span>
      </h2>
      <div className="muted mb12">
        上传企业内部文档（SOP、维修记录、FMEA、工艺规程），系统 LLM 预标注后由人工审核确认，确保知识准确性。
      </div>

      <div className="g2 mb12">
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
            <h3 style={{ marginBottom: 0 }}>文档队列</h3>
            <button type="button" className="btn btn-sm" onClick={() => { loadList(); if (selectedId) loadDetail(selectedId) }} disabled={loadingList}>
              <RefreshCw style={{ width: 12, height: 12 }} />
            </button>
          </div>
          <div id="doc-queue" className="mt8">
            {loadingList ? (
              <p className="muted">加载中…</p>
            ) : summaries.length === 0 ? (
              <p className="muted">暂无文档，请上传。</p>
            ) : (
              summaries.map((d) => (
                <div
                  key={d.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '7px 0',
                    borderBottom: '0.5px solid var(--b1)',
                    fontSize: 12,
                    cursor: 'pointer',
                  }}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedId(d.id)}
                  onKeyDown={(e) => e.key === 'Enter' && setSelectedId(d.id)}
                >
                  <div className={`sdot ${statusDotClass(d.status)}`} />
                  <div style={{ flex: 1, fontWeight: selectedId === d.id ? 500 : 400 }}>{d.filename}</div>
                  <div className="muted">
                    {d.pending_count != null ? `${d.pending_count}条待审` : d.status}
                    {d.approved_count != null ? ` / ${d.approved_count}已审` : ''}
                  </div>
                </div>
              ))
            )}
          </div>
          <label className="upz mt8" style={{ display: 'block', position: 'relative' }}>
            <div style={{ fontSize: 18, marginBottom: 6, color: 'var(--t3)' }}>↑</div>
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--t1)' }}>{uploading ? '上传中…' : '点击上传企业文档'}</div>
            <div className="muted" style={{ marginTop: 4 }}>
              支持 PDF · Word · Excel · TXT
            </div>
            <input
              type="file"
              onChange={handleUpload}
              disabled={uploading}
              style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer', width: '100%', height: '100%' }}
            />
          </label>
        </div>

        <div className="card">
          <h3>预标注处理统计</h3>
          <div className="g2 mt8">
            <div className="stat">
              <div className="stat-v" style={{ color: 'var(--blue)' }}>
                {stats.n}
              </div>
              <div className="stat-l">已处理文档</div>
            </div>
            <div className="stat">
              <div className="stat-v" style={{ color: 'var(--amber)' }}>
                {stats.pending}
              </div>
              <div className="stat-l">待审核关系</div>
            </div>
            <div className="stat">
              <div className="stat-v" style={{ color: 'var(--green)' }}>
                {stats.approved}
              </div>
              <div className="stat-l">已确认关系</div>
            </div>
            <div className="stat">
              <div className="stat-v" style={{ color: 'var(--red)' }}>
                {stats.rejected}
              </div>
              <div className="stat-l">已拒绝关系（估算）</div>
            </div>
          </div>
          <div className="div" />
          <div style={{ fontSize: 11, color: 'var(--t2)', lineHeight: 1.7 }}>
            LLM 预标注准确率（基于已审核）：<strong style={{ color: 'var(--green)' }}>—</strong>
            <br />
            数据来自当前列表汇总；细粒度准确率待 metrics 接口接入。
          </div>
        </div>
      </div>

      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
          <h3 style={{ marginBottom: 0 }}>
            标注工作区 · <span style={{ color: 'var(--blue)' }}>{displayName}</span>
          </h3>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <button type="button" className="btn btn-sm btn-ok" disabled={busy || !selectedId || pendingRels.length === 0} onClick={batchApproveAllPending}>
              批量通过
            </button>
            <button type="button" className="btn btn-sm btn-p" disabled={busy || !selectedId || detail?.status === 'committed'} onClick={handleCommit}>
              提交已审核
            </button>
          </div>
        </div>

        <div className="muted mb8" style={{ fontSize: 11 }}>
          标注人 ID{' '}
          <input type="text" value={engineerId} onChange={(e) => setEngineerId(e.target.value)} style={{ width: 140, marginLeft: 6 }} />
        </div>

        <div className="doc-chunk mb8">
          当 <span className="ent-span ent-machine">1号注塑机</span> 发生 <span className="ent-span ent-alarm">过热报警</span> 时，最常见的根本原因是{' '}
          <span className="ent-span ent-issue">轴承磨损</span>
          ，尤其在环境温度高于 35°C 的条件下。处理步骤包括：立即降低 <span className="ent-span ent-machine">1号注塑机</span> 转速，检查{' '}
          <span className="ent-span ent-issue">冷却液水位</span>，并通知维修班组创建 <span className="ent-span ent-wo">维修工单</span>。
        </div>
        <div className="doc-chunk mb8">
          历史数据表明，<span className="ent-span ent-alarm">振动报警</span> 与 <span className="ent-span ent-issue">轴承磨损</span> 的关联度达到
          91%，建议在 <span className="ent-span ent-alarm">振动报警</span> 出现后 30 分钟内完成轴承检查，否则可能导致{' '}
          <span className="ent-span ent-wo">生产工单</span> 延误。
        </div>
        {detail?.extracted_text ? (
          <div className="doc-chunk mb8" style={{ whiteSpace: 'pre-wrap' }}>
            {detail.extracted_text}
          </div>
        ) : null}

        <h3 style={{ marginBottom: 7 }}>LLM 预标注关系 · 待审核</h3>
        {!selectedId ? (
          <p className="muted">请选择左侧文档。</p>
        ) : loadingDetail ? (
          <p className="muted">加载详情…</p>
        ) : !detail ? (
          <p className="muted">无法加载该文档。</p>
        ) : (
          <>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
              <button type="button" className="btn btn-sm" disabled={pendingRels.length === 0 || busy} onClick={selectAllPending}>
                全选待审
              </button>
              <button type="button" className="btn btn-sm" disabled={selectedRelIds.size === 0 || busy} onClick={clearSelection}>
                清除选择
              </button>
              <button type="button" className="btn btn-sm btn-ok" disabled={selectedRelIds.size === 0 || busy} onClick={() => batchAnnotate('approve')}>
                批量批准（所选）
              </button>
              <button type="button" className="btn btn-sm btn-no" disabled={selectedRelIds.size === 0 || busy} onClick={() => batchAnnotate('reject')}>
                批量拒绝（所选）
              </button>
            </div>
            <div id="doc-rels">
              {(detail.extracted_relations || []).map((rel) => {
                const pending = isRelationPending(rel)
                const checked = selectedRelIds.has(rel.id)
                const c = Number(rel.effective_confidence ?? rel.confidence ?? 0)
                const oneApprove = async () => {
                  setBusy(true)
                  try {
                    await annotateDocumentRelation(selectedId, rel.id, { action: 'approve', annotated_by: engineerId })
                    await loadDetail(selectedId)
                    await loadList()
                  } catch (e) {
                    setMsg({ type: 'err', text: e.message || '操作失败' })
                  } finally {
                    setBusy(false)
                  }
                }
                const oneReject = async () => {
                  setBusy(true)
                  try {
                    await annotateDocumentRelation(selectedId, rel.id, { action: 'reject', annotated_by: engineerId })
                    await loadDetail(selectedId)
                    await loadList()
                  } catch (e) {
                    setMsg({ type: 'err', text: e.message || '操作失败' })
                  } finally {
                    setBusy(false)
                  }
                }
                return (
                  <div key={rel.id} className={`rel-pending ${relStatusClass(rel)}`}>
                    {pending ? (
                      <button type="button" aria-label={checked ? '取消选择' : '选择'} onClick={() => toggleRel(rel.id)} style={{ padding: 2, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--t1)' }}>
                        {checked ? <CheckSquare style={{ width: 18, height: 18 }} /> : <Square style={{ width: 18, height: 18 }} />}
                      </button>
                    ) : (
                      <span style={{ width: 22 }} />
                    )}
                    <span className="rnode" style={{ fontSize: 10 }}>
                      {rel.source_node_name || rel.source_node_id}
                    </span>
                    <span style={{ fontSize: 10, color: 'var(--t2)' }}>→ {rel.relation_type} →</span>
                    <span className="rnode" style={{ fontSize: 10 }}>
                      {rel.target_node_name || rel.target_node_id}
                    </span>
                    <span className="badge b-gray" style={{ fontSize: 9 }}>
                      {rel.evidence?.slice(0, 12) || '通用'}
                    </span>
                    <div className="cbar" style={{ flex: 1, maxWidth: 60 }}>
                      <div className={`cfill ${c >= 0.8 ? 'cf-high' : 'cf-mid'}`} style={{ width: `${Math.min(100, c * 100)}%` }} />
                    </div>
                    <span style={{ fontSize: 10, minWidth: 28 }}>{c.toFixed(2)}</span>
                    {pending ? (
                      <>
                        <button type="button" className="btn btn-ok btn-sm" disabled={busy} onClick={oneApprove}>
                          ✓
                        </button>
                        <button type="button" className="btn btn-no btn-sm" disabled={busy} onClick={oneReject}>
                          ✗
                        </button>
                        <button type="button" className="btn btn-sm" style={{ fontSize: 10 }} disabled={busy} onClick={() => window.alert('修改功能开发中')}>
                          ✎
                        </button>
                      </>
                    ) : rel.annotation_status?.toLowerCase() === 'approved' ? (
                      <span className="badge b-green">已通过</span>
                    ) : (
                      <span className="badge b-red">已拒绝</span>
                    )}
                  </div>
                )
              })}
            </div>
            {detail.extracted_relations?.length === 0 && <p className="muted">暂无抽取候选关系。</p>}
          </>
        )}
      </div>

      {msg && (
        <p
          className="mt8"
          style={{
            fontSize: 12,
            padding: '8px 10px',
            borderRadius: 8,
            background: msg.type === 'ok' ? 'var(--green-l)' : 'var(--red-l)',
            color: msg.type === 'ok' ? 'var(--green)' : 'var(--red)',
          }}
        >
          {msg.text}
        </p>
      )}
    </div>
  )
}
