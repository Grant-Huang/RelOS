/**
 * 提示标注工作区 — 对齐 docs/relos_workbench_v2.html #v-rt-prompt
 * chip 筛选 + ann-card 队列 + POST /relations/{id}/feedback
 */
import { useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { listPendingRelations, submitRelationFeedback } from '../../api/client'

const ENGINEER_KEY = 'relos_engineer_id'

function inPromptRange(c) {
  return c >= 0.5 && c <= 0.79
}

function relationCategory(rel) {
  const t = `${rel.relation_type || ''} ${rel.source_text || ''} ${rel.source_node_id || ''} ${rel.target_node_id || ''}`.toUpperCase()
  if (t.includes('WORKORDER') || t.includes('工单') || t.includes('WO')) return 'wo'
  if (
    t.includes('QUALITY') ||
    t.includes('DEFECT') ||
    t.includes('BATCH') ||
    t.includes('质量') ||
    t.includes('工艺') ||
    t.includes('PROCESS')
  )
    return 'quality'
  if (t.includes('ALARM') || t.includes('报警') || t.includes('告警')) return 'alarm'
  return 'alarm'
}

function shortRelationName(relType) {
  if (!relType) return '—'
  const parts = relType.split('__')
  if (parts.length >= 3) return parts[1]
  return relType.replace(/_/g, ' ').slice(0, 16)
}

function whyText(rel) {
  const c = Number(rel.confidence)
  if (c < 0.65) return '证据不足或观测次数少'
  if (c < 0.75) return '与历史案例部分匹配'
  return '间接影响，置信度中等'
}

export default function PromptLabeling() {
  const [relations, setRelations] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [filterCat, setFilterCat] = useState('all')
  const [processed, setProcessed] = useState(new Set())
  const [engineerId, setEngineerId] = useState(() => {
    try {
      return localStorage.getItem(ENGINEER_KEY) || 'operator-1'
    } catch {
      return 'operator-1'
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(ENGINEER_KEY, engineerId)
    } catch {
      /* ignore */
    }
  }, [engineerId])

  const load = async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const data = await listPendingRelations(80)
      const items = Array.isArray(data) ? data : []
      setRelations(items)
      if (items.length === 0) {
        setLoadError(null)
      }
    } catch (e) {
      setRelations([])
      setLoadError(e.message || '加载待审队列失败，请确认后端与 Neo4j 已启动。')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const pool = useMemo(() => {
    return relations.filter((r) => !processed.has(r.id) && inPromptRange(Number(r.confidence)))
  }, [relations, processed])

  const counts = useMemo(() => {
    const c = { all: 0, alarm: 0, quality: 0, wo: 0 }
    pool.forEach((r) => {
      c.all += 1
      const cat = relationCategory(r)
      if (cat === 'alarm') c.alarm += 1
      else if (cat === 'quality') c.quality += 1
      else if (cat === 'wo') c.wo += 1
    })
    return c
  }, [pool])

  const visible = useMemo(() => {
    if (filterCat === 'all') return pool
    return pool.filter((r) => relationCategory(r) === filterCat)
  }, [pool, filterCat])

  const doFeedback = async (id, confirmed) => {
    try {
      await submitRelationFeedback(id, { engineer_id: engineerId, confirmed })
    } catch {
      /* 仍标记本地已处理，避免界面卡住 */
    }
    setProcessed((prev) => new Set([...prev, id]))
  }

  const approveAll = async () => {
    if (visible.length === 0) return
    const ids = visible.map((r) => r.id)
    if (!window.confirm(`将确认并反馈 ${ids.length} 条关系，是否继续？`)) return
    for (const id of ids) {
      try {
        await submitRelationFeedback(id, { engineer_id: engineerId, confirmed: true })
      } catch {
        /* 仍合并进已处理 */
      }
    }
    setProcessed((prev) => {
      const next = new Set(prev)
      ids.forEach((id) => next.add(id))
      return next
    })
  }

  const skipAll = () => {
    if (visible.length === 0) return
    setProcessed((prev) => {
      const next = new Set(prev)
      visible.forEach((r) => next.add(r.id))
      return next
    })
  }

  const chipCls = (cat) => `chip${filterCat === cat ? ' on' : ''}`

  return (
    <div className="relos-page">
      <h2>
        提示标注工作区 <span className="badge b-amber">置信度 0.50–0.79 · 需人工确认</span>
      </h2>
      <div className="muted mb12">以下关系系统无法自信地判断，请您结合现场经验确认。每次确认都会强化系统的学习。</div>

      <div className="card mb10">
        <div className="muted" style={{ marginBottom: 6 }}>
          操作员工号（用于反馈审计）
        </div>
        <input type="text" value={engineerId} onChange={(e) => setEngineerId(e.target.value)} placeholder="operator-1" style={{ maxWidth: 220 }} />
        <button type="button" className="btn btn-sm" style={{ marginLeft: 8 }} onClick={load} disabled={loading}>
          <RefreshCw style={{ width: 12, height: 12 }} /> 刷新队列
        </button>
      </div>

      {loadError ? (
        <div className="card mb10" style={{ borderColor: 'var(--red)', background: 'var(--red-l)' }}>
          <p style={{ fontSize: 12, color: 'var(--red)', margin: 0 }}>{loadError}</p>
        </div>
      ) : null}

      {!loading && !loadError && relations.length === 0 ? (
        <div className="card mb10">
          <p className="muted" style={{ fontSize: 12, margin: 0 }}>
            当前没有 pending_review 关系。请运行 <code style={{ fontSize: 11 }}>python scripts/seed_demo_scenarios.py</code>{' '}
           （需先执行 seed_neo4j）以注入演示待审数据。
          </p>
        </div>
      ) : null}

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
        <span className="muted">筛选：</span>
        <div id="ann-filter">
          <span role="button" tabIndex={0} className={chipCls('all')} onClick={() => setFilterCat('all')} onKeyDown={(e) => e.key === 'Enter' && setFilterCat('all')}>
            全部 ({counts.all})
          </span>
          <span role="button" tabIndex={0} className={chipCls('alarm')} onClick={() => setFilterCat('alarm')} onKeyDown={(e) => e.key === 'Enter' && setFilterCat('alarm')}>
            报警类 ({counts.alarm})
          </span>
          <span role="button" tabIndex={0} className={chipCls('quality')} onClick={() => setFilterCat('quality')} onKeyDown={(e) => e.key === 'Enter' && setFilterCat('quality')}>
            质量类 ({counts.quality})
          </span>
          <span role="button" tabIndex={0} className={chipCls('wo')} onClick={() => setFilterCat('wo')} onKeyDown={(e) => e.key === 'Enter' && setFilterCat('wo')}>
            工单类 ({counts.wo})
          </span>
        </div>
        <div style={{ flex: 1 }} />
        <button type="button" className="btn btn-sm btn-ok" onClick={approveAll}>
          全部确认
        </button>
        <button type="button" className="btn btn-sm" onClick={skipAll}>
          跳过全部
        </button>
      </div>

      <div id="ann-queue">
        {loading ? (
          <div className="muted" style={{ textAlign: 'center', padding: 20 }}>
            加载中…
          </div>
        ) : visible.length === 0 ? (
          <div className="muted" style={{ textAlign: 'center', padding: 20 }}>
            {pool.length === 0 ? '提示区内暂无待处理项（或已全部处理）' : '当前筛选下无待处理项'}
          </div>
        ) : (
          visible.map((a) => {
            const c = Number(a.confidence)
            const cat = relationCategory(a)
            const catLabel = cat === 'alarm' ? '报警类' : cat === 'quality' ? '质量类' : '工单类'
            const badgeCls = c < 0.65 ? 'b-red' : c < 0.75 ? 'b-amber' : 'b-blue'
            const cfCls = c < 0.65 ? 'cf-low' : c < 0.75 ? 'cf-mid' : 'cf-high'
            const src = a.provenance_detail || a.source_text || `${a.provenance || '图谱'} · 待审核`
            return (
              <div key={a.id} className="ann-card" id={`ac-${a.id}`}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span className={`badge ${badgeCls}`}>{c.toFixed(2)} 置信度</span>
                    <span className="badge b-gray">{catLabel}</span>
                  </div>
                  <span style={{ fontSize: 10, color: 'var(--t3)' }}>不确定原因：{whyText(a)}</span>
                </div>
                <div className="ann-src" style={{ marginBottom: 8 }}>
                  来源：{src}
                </div>
                <div className="rrow" style={{ marginBottom: 8 }}>
                  <span className="rnode">{a.source_node_id}</span>
                  <span style={{ fontSize: 11, color: 'var(--t2)' }}>→ {shortRelationName(a.relation_type)} →</span>
                  <span className="rnode">{a.target_node_id}</span>
                  <div className="cbar" style={{ flex: 1 }}>
                    <div className={`cfill ${cfCls}`} style={{ width: `${c * 100}%` }} />
                  </div>
                </div>
                <div className="ann-actions">
                  <button type="button" className="btn btn-ok btn-sm" onClick={() => doFeedback(a.id, true)}>
                    ✓ 正确，写入
                  </button>
                  <button type="button" className="btn btn-no btn-sm" onClick={() => doFeedback(a.id, false)}>
                    ✗ 错误
                  </button>
                  <button type="button" className="btn btn-sm" onClick={() => window.alert('请在后续版本中选择正确关系类型')}>
                    ✎ 修改关系类型
                  </button>
                  <button type="button" className="btn btn-sm" onClick={() => setProcessed((p) => new Set([...p, a.id]))}>
                    跳过
                  </button>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
