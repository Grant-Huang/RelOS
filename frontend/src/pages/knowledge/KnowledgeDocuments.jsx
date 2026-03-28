/**
 * 企业文档（层 3）：文档列表、候选关系批审、提交图谱
 */
import { useCallback, useEffect, useState } from 'react'
import { Files, RefreshCw, CheckSquare, Square, Upload } from 'lucide-react'
import LayerAuthorityBar from '../../components/LayerAuthorityBar'
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

  return (
    <div className="wb-main p-4 md:p-8 max-w-6xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          <Files className="w-7 h-7 flex-shrink-0" style={{ color: 'var(--wb-teal)' }} />
          <div>
            <h1 className="text-xl md:text-2xl font-semibold" style={{ color: 'var(--wb-text)' }}>
              企业文档标注
            </h1>
            <p className="text-sm wb-text-muted">层 3 · SOP / 工单 / FMEA 等，批审后提交图谱</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="wb-btn-ghost inline-flex items-center gap-2 cursor-pointer min-h-[44px]">
            <Upload className="w-4 h-4" />
            {uploading ? '上传中…' : '上传文档'}
            <input type="file" className="hidden" onChange={handleUpload} disabled={uploading} />
          </label>
          <button
            type="button"
            onClick={() => {
              loadList()
              if (selectedId) loadDetail(selectedId)
            }}
            disabled={loadingList}
            className="wb-btn-ghost inline-flex items-center gap-2 min-h-[44px]"
          >
            <RefreshCw className={`w-4 h-4 ${loadingList ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>
      </div>

      <LayerAuthorityBar layer={3} />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="text-xs wb-text-muted">标注人 ID</label>
        <input
          value={engineerId}
          onChange={(e) => setEngineerId(e.target.value)}
          className="wb-input max-w-xs"
          placeholder="engineer_id"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 wb-card p-3 max-h-[480px] overflow-y-auto">
          <h2 className="text-xs font-semibold wb-text-muted uppercase mb-2">文档列表</h2>
          {loadingList ? (
            <p className="text-sm wb-text-muted">加载中…</p>
          ) : summaries.length === 0 ? (
            <p className="text-sm wb-text-muted">暂无文档，请先上传。</p>
          ) : (
            <ul className="space-y-1">
              {summaries.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(s.id)}
                    className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors min-h-[44px] ${
                      selectedId === s.id
                        ? 'bg-[color:var(--wb-blue-soft)] font-medium'
                        : 'hover:bg-[color:var(--wb-surface-2)]'
                    }`}
                    style={{ color: 'var(--wb-text)' }}
                  >
                    <span className="line-clamp-2">{s.filename}</span>
                    <span className="block text-[10px] wb-text-muted mt-0.5">
                      {s.status} · 待审 {s.pending_count ?? '—'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="lg:col-span-2 wb-card p-4">
          {!selectedId ? (
            <p className="text-sm wb-text-muted">请选择左侧文档。</p>
          ) : loadingDetail ? (
            <p className="text-sm wb-text-muted">加载详情…</p>
          ) : !detail ? (
            <p className="text-sm wb-text-muted">无法加载该文档。</p>
          ) : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-2 mb-4">
                <div>
                  <h2 className="text-lg font-semibold" style={{ color: 'var(--wb-text)' }}>
                    {detail.filename}
                  </h2>
                  <p className="text-xs wb-text-muted mt-1">
                    状态 {detail.status} · 模板 {detail.template_type}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={busy || detail.status === 'committed'}
                  onClick={handleCommit}
                  className="wb-btn-primary min-h-[44px] disabled:opacity-40"
                >
                  提交到图谱
                </button>
              </div>

              <div className="flex flex-wrap gap-2 mb-4">
                <button
                  type="button"
                  onClick={selectAllPending}
                  disabled={pendingRels.length === 0 || busy}
                  className="wb-btn-ghost text-sm min-h-[44px]"
                >
                  全选待审
                </button>
                <button
                  type="button"
                  onClick={clearSelection}
                  disabled={selectedRelIds.size === 0 || busy}
                  className="wb-btn-ghost text-sm min-h-[44px]"
                >
                  清除选择
                </button>
                <button
                  type="button"
                  onClick={() => batchAnnotate('approve')}
                  disabled={selectedRelIds.size === 0 || busy}
                  className="wb-btn-success text-sm min-h-[44px] disabled:opacity-40"
                >
                  批量批准
                </button>
                <button
                  type="button"
                  onClick={() => batchAnnotate('reject')}
                  disabled={selectedRelIds.size === 0 || busy}
                  className="wb-btn-danger text-sm min-h-[44px] disabled:opacity-40"
                >
                  批量拒绝
                </button>
              </div>

              <ul className="space-y-2">
                {(detail.extracted_relations || []).map((rel) => {
                  const pending = isRelationPending(rel)
                  const checked = selectedRelIds.has(rel.id)
                  return (
                    <li
                      key={rel.id}
                      className="wb-card-muted p-3 rounded-lg flex gap-3 items-start"
                    >
                      {pending ? (
                        <button
                          type="button"
                          aria-label={checked ? '取消选择' : '选择'}
                          onClick={() => toggleRel(rel.id)}
                          className="mt-0.5 p-1 text-[color:var(--wb-text)]"
                        >
                          {checked ? (
                            <CheckSquare className="w-5 h-5" />
                          ) : (
                            <Square className="w-5 h-5" />
                          )}
                        </button>
                      ) : (
                        <span className="w-7 flex-shrink-0" />
                      )}
                      <div className="flex-1 min-w-0 text-sm">
                        <p className="font-medium wb-text-secondary">
                          {rel.relation_type}{' '}
                          <span className="text-xs wb-text-muted">
                            · {rel.annotation_status} · conf {rel.effective_confidence ?? rel.confidence}
                          </span>
                        </p>
                        <p className="text-xs wb-text-muted mt-1 break-words">
                          {rel.source_node_name} → {rel.target_node_name}
                        </p>
                        {rel.evidence ? (
                          <p className="text-xs mt-2 wb-text-secondary line-clamp-3">{rel.evidence}</p>
                        ) : null}
                      </div>
                    </li>
                  )
                })}
              </ul>

              {detail.extracted_relations?.length === 0 && (
                <p className="text-sm wb-text-muted">暂无抽取候选关系。</p>
              )}
            </>
          )}
        </div>
      </div>

      {msg && (
        <p
          className={`mt-4 text-sm rounded-lg px-3 py-2 ${
            msg.type === 'ok'
              ? 'bg-[color:var(--wb-green-soft)]'
              : 'bg-[color:var(--wb-red-soft)] text-[color:var(--wb-red)]'
          }`}
          style={msg.type === 'ok' ? { color: 'var(--wb-green)' } : undefined}
        >
          {msg.text}
        </p>
      )}
    </div>
  )
}
