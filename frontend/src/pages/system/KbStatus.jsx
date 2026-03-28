/**
 * 知识库状态 — 对齐 docs/relos_workbench_v2.html #v-kb-status
 * 指标与分布来自 GET /v1/metrics（Neo4j 聚合）
 */
import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { getMetrics, listDocuments } from '../../api/client'

function normalizeDocList(raw) {
  if (Array.isArray(raw)) return raw
  if (raw?.documents && Array.isArray(raw.documents)) return raw.documents
  return []
}

function fmtNum(v) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (Number.isFinite(n) && n >= 1000) return n.toLocaleString('zh-CN')
  return String(v)
}

const PROV_LABEL = {
  sensor_realtime: 'IoT 自动抽取',
  llm_extracted: 'LLM / 文档抽取',
  manual_engineer: '专家直接输入',
  mes_structured: 'MES 结构化',
  inference: '系统推断',
  structured_document: '企业文档',
  expert_document: '专家文档',
  unknown: '其他',
}

const PHASE_META = {
  bootstrap: { name: '层 1 · 公开知识', color: 'var(--blue)' },
  interview: { name: '层 2 · 专家知识', color: 'var(--purple)' },
  pretrain: { name: '层 3 · 企业/预训练', color: 'var(--teal)' },
  runtime: { name: '运行时知识', color: 'var(--green)' },
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

  const totalRel = metrics?.total_relations
  const active = metrics?.active_count
  const pendingReview = metrics?.pending_review_count
  const archived = metrics?.archived_count

  const avgConf = metrics?.avg_confidence ?? metrics?.average_confidence

  const provRows = metrics?.provenance_breakdown || []
  const maxProv = Math.max(1, ...provRows.map((p) => p.count))

  const rtRows = metrics?.relation_type_breakdown || []

  const phaseRows = metrics?.knowledge_phase_breakdown || []

  return (
    <div className="relos-page">
      <h2>
        知识库状态 <span className="badge b-green">● 运行中</span>
      </h2>

      {err ? (
        <p className="muted mb12" style={{ color: 'var(--red)' }}>
          {err}
        </p>
      ) : null}

      <div className="g4 mb12" style={{ marginBottom: 12 }}>
        <div className="stat">
          <div className="stat-v" style={{ color: 'var(--blue)' }}>
            {loading ? '…' : fmtNum(active ?? totalRel)}
          </div>
          <div className="stat-l">活跃关系总数</div>
        </div>
        <div className="stat">
          <div className="stat-v" style={{ color: 'var(--green)' }}>
            {loading ? '…' : avgConf != null ? Number(avgConf).toFixed(2) : '—'}
          </div>
          <div className="stat-l">平均置信度</div>
        </div>
        <div className="stat">
          <div className="stat-v" style={{ color: 'var(--amber)' }}>
            {loading ? '…' : fmtNum(pendingReview)}
          </div>
          <div className="stat-l">待审核关系</div>
        </div>
        <div className="stat">
          <div className="stat-v" style={{ color: 'var(--t2)' }}>
            {loading ? '…' : fmtNum(archived)}
          </div>
          <div className="stat-l">已衰减废弃</div>
        </div>
      </div>

      <div style={{ marginBottom: 10 }}>
        <button type="button" className="btn btn-sm" onClick={load} disabled={loading}>
          <RefreshCw style={{ width: 12, height: 12 }} /> 刷新
        </button>
      </div>

      <div className="g2 mb10">
        <div className="card">
          <h3>来源分布（图谱 provenance）</h3>
          {!provRows.length ? (
            <p className="muted mt8" style={{ fontSize: 12 }}>
              暂无数据。注入 seed 后刷新可见。
            </p>
          ) : (
            <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {provRows.map((p) => {
                const label = PROV_LABEL[p.provenance] || p.provenance
                const w = Math.round((p.count / maxProv) * 100)
                return (
                  <div key={p.provenance}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
                      <span>{label}</span>
                      <span className="badge b-blue">{fmtNum(p.count)} 条</span>
                    </div>
                    <div className="cbar">
                      <div className="cfill cf-high" style={{ width: `${w}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
        <div className="card">
          <h3>关系类型分布（Top 8）</h3>
          {!rtRows.length ? (
            <p className="muted mt8" style={{ fontSize: 12 }}>
              暂无关系数据。
            </p>
          ) : (
            <table className="tbl mt8">
              <thead>
                <tr>
                  <th>关系类型</th>
                  <th>数量</th>
                  <th>平均置信度</th>
                </tr>
              </thead>
              <tbody>
                {rtRows.map((r) => (
                  <tr key={r.relation_type}>
                    <td>
                      <span className="badge b-blue" style={{ fontSize: 10 }}>
                        {r.relation_type}
                      </span>
                    </td>
                    <td style={{ fontWeight: 500 }}>{fmtNum(r.count)}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        <div className="cbar" style={{ width: 60 }}>
                          <div
                            className="cfill cf-high"
                            style={{ width: `${Math.min(100, Number(r.avg_confidence) * 100)}%` }}
                          />
                        </div>
                        <span style={{ fontSize: 11 }}>{Number(r.avg_confidence).toFixed(2)}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="card mb10">
        <h3>知识结构（按 knowledge_phase）</h3>
        {!phaseRows.length ? (
          <p className="muted mt8" style={{ fontSize: 12 }}>
            暂无阶段字段数据（旧数据可能仅有默认 bootstrap）。
          </p>
        ) : (
          <div className="g3 mt8" id="layer-health">
            {phaseRows.map((row) => {
              const meta = PHASE_META[row.phase] || {
                name: row.phase,
                color: 'var(--t2)',
              }
              const cov =
                totalRel && row.count
                  ? `${((row.count / totalRel) * 100).toFixed(1)}%`
                  : '—'
              const st = Number(row.avg_confidence) >= 0.72 ? '健康' : '需补充'
              return (
                <div key={row.phase} className="stat" style={{ borderLeft: `3px solid ${meta.color}` }}>
                  <div style={{ fontSize: 11, fontWeight: 500, color: meta.color, marginBottom: 6 }}>{meta.name}</div>
                  <div style={{ fontSize: 19, fontWeight: 500, marginBottom: 3 }}>{fmtNum(row.count)}条</div>
                  <div className="muted" style={{ fontSize: 10 }}>
                    占全库关系：{cov}
                  </div>
                  <div className="muted" style={{ fontSize: 10 }}>
                    平均置信度：{Number(row.avg_confidence).toFixed(2)}
                  </div>
                  <div style={{ marginTop: 6 }}>
                    <span className={`badge ${st === '健康' ? 'b-green' : 'b-amber'}`}>{st}</span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div className="card">
        <h3>最近文档（API）</h3>
        {loading ? (
          <p className="muted mt8">加载中…</p>
        ) : docs.length === 0 ? (
          <p className="muted mt8">暂无文档记录。</p>
        ) : (
          <ul className="mt8" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {docs.slice(0, 20).map((d) => (
              <li key={d.id} style={{ padding: '8px 0', borderBottom: '0.5px solid var(--b1)', fontSize: 12 }}>
                <div style={{ fontWeight: 500 }}>{d.filename}</div>
                <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
                  {d.status} · 待标注 {d.pending_count ?? 0} · 已批 {d.approved_count ?? 0} · 已提交 {d.committed_count ?? 0}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
