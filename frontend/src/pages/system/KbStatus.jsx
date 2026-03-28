/**
 * 知识库状态：指标 + 文档摘要列表
 */
import { useEffect, useState } from 'react'
import { Database, RefreshCw } from 'lucide-react'
import { getMetrics, listDocuments } from '../../api/client'

function normalizeDocList(raw) {
  if (Array.isArray(raw)) return raw
  if (raw?.documents && Array.isArray(raw.documents)) return raw.documents
  return []
}

export default function KbStatus() {
  const [metrics, setMetrics] = useState(null)
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const [m, dRaw] = await Promise.all([
        getMetrics().catch(() => null),
        listDocuments().catch(() => []),
      ])
      setMetrics(m)
      setDocs(normalizeDocList(dRaw))
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const pendingReview = metrics?.pending_review_count ?? '—'
  const totalRel = metrics?.total_relations ?? '—'
  const active = metrics?.active_count ?? '—'

  return (
    <div className="wb-main p-4 md:p-8 max-w-4xl mx-auto">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div className="flex items-center gap-3">
          <Database className="w-7 h-7 flex-shrink-0" style={{ color: 'var(--wb-blue)' }} />
          <div>
            <h1 className="text-xl md:text-2xl font-semibold" style={{ color: 'var(--wb-text)' }}>
              知识库状态
            </h1>
            <p className="text-sm wb-text-muted">图谱指标与文档摄取摘要</p>
          </div>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="wb-btn-ghost inline-flex items-center gap-2 min-h-[44px]"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {err && (
        <p className="text-sm text-[color:var(--wb-red)] mb-4 px-3 py-2 rounded-lg bg-[color:var(--wb-red-soft)]">
          {err}
        </p>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-8">
        <div className="wb-card p-4 min-h-[88px]">
          <p className="text-2xl font-semibold tabular-nums wb-text-secondary">{totalRel}</p>
          <p className="text-xs wb-text-muted mt-1">关系总数</p>
        </div>
        <div className="wb-card p-4 min-h-[88px]">
          <p className="text-2xl font-semibold tabular-nums" style={{ color: 'var(--wb-green)' }}>
            {active}
          </p>
          <p className="text-xs wb-text-muted mt-1">已激活</p>
        </div>
        <div className="wb-card p-4 min-h-[88px] col-span-2 md:col-span-1">
          <p className="text-2xl font-semibold tabular-nums" style={{ color: 'var(--wb-amber)' }}>
            {pendingReview}
          </p>
          <p className="text-xs wb-text-muted mt-1">待审核（图谱）</p>
        </div>
      </div>

      <h2 className="text-sm font-semibold wb-text-secondary mb-2">最近文档</h2>
      <div className="wb-card overflow-hidden">
        {loading ? (
          <p className="p-4 text-sm wb-text-muted">加载中…</p>
        ) : docs.length === 0 ? (
          <p className="p-4 text-sm wb-text-muted">暂无文档记录。</p>
        ) : (
          <ul className="divide-y" style={{ borderColor: 'var(--wb-border)' }}>
            {docs.slice(0, 30).map((d) => (
              <li key={d.id} className="px-4 py-3 text-sm">
                <p className="font-medium wb-text-secondary line-clamp-1">{d.filename}</p>
                <p className="text-xs wb-text-muted mt-1">
                  {d.status} · 待标注 {d.pending_count ?? 0} · 已批 {d.approved_count ?? 0} · 已提交{' '}
                  {d.committed_count ?? 0}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
