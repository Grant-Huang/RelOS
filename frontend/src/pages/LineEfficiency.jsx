/**
 * 产线效率 / 跨部门 / 异常处理（S-07/08/09）— 版式对齐 workbench v2
 * 数据仅来自 /v1/scenarios/*，失败或空数据展示提示（不注入前端假数据）
 */
import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { getLineEfficiency, getCrossDeptAnalysis, getIssueResolution } from '../api/client'

function LineBar({ line, isBottleneck, onClick, expanded, rootPath, contributionPct }) {
  const pct = Math.min(100, Math.max(0, Number(line.efficiency_pct) || 0))
  const fillClass = isBottleneck ? 'cf-low' : pct >= 85 ? 'cf-high' : 'cf-mid'
  const inner = (
    <>
      <div className="rrow" style={{ marginBottom: 8, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
          <span className="rnode">{line.name || line.line_id}</span>
          {isBottleneck ? <span className="badge b-red">瓶颈</span> : <span className="badge b-gray">正常</span>}
        </div>
        <span className="tabular-nums stat-v" style={{ marginBottom: 0, fontSize: 18, color: 'var(--t1)' }}>
          {pct}%
        </span>
      </div>
      <div className="cbar" style={{ height: 6 }}>
        <div className={`cfill ${fillClass}`} style={{ width: `${pct}%` }} />
      </div>
    </>
  )

  return (
    <div className="mb10">
      {isBottleneck ? (
        <button type="button" className="card" onClick={onClick} style={{ width: '100%', textAlign: 'left', borderColor: 'var(--red)', background: 'var(--red-l)' }}>
          {inner}
        </button>
      ) : (
        <div className="card">{inner}</div>
      )}

      {isBottleneck && expanded && rootPath?.length > 0 && (
        <div className="card mt8" style={{ borderColor: 'var(--red)', background: 'var(--red-l)' }}>
          <h3 style={{ marginBottom: 6 }}>根因路径</h3>
          <div style={{ marginTop: 8 }}>
            {rootPath.map((step, i) => (
              <div key={i} className="tl-item">
                <span className="tl-dot" style={{ background: 'var(--red)' }} />
                <span style={{ fontSize: 12, color: 'var(--t1)', lineHeight: 1.5 }}>{step}</span>
              </div>
            ))}
          </div>
          <p style={{ fontSize: 12, color: 'var(--red)', marginTop: 10, marginBottom: 0 }}>
            瓶颈贡献度：<strong>{contributionPct}%</strong> 的总延误
          </p>
        </div>
      )}
    </div>
  )
}

export default function LineEfficiency() {
  const [lineData, setLineData] = useState(null)
  const [resolutionData, setResolutionData] = useState(null)
  const [crossData, setCrossData] = useState(null)
  const [lineErr, setLineErr] = useState(null)
  const [resolutionErr, setResolutionErr] = useState(null)
  const [crossErr, setCrossErr] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expandedLine, setExpandedLine] = useState(null)

  const load = async () => {
    setLoading(true)
    setLineErr(null)
    setResolutionErr(null)
    setCrossErr(null)
    const [lr, rr, cr] = await Promise.all([
      getLineEfficiency().then(
        (d) => ({ ok: true, d }),
        (e) => ({ ok: false, e: e.message || '加载失败' }),
      ),
      getIssueResolution().then(
        (d) => ({ ok: true, d }),
        (e) => ({ ok: false, e: e.message || '加载失败' }),
      ),
      getCrossDeptAnalysis().then(
        (d) => ({ ok: true, d }),
        (e) => ({ ok: false, e: e.message || '加载失败' }),
      ),
    ])
    if (lr.ok) setLineData(lr.d)
    else {
      setLineData(null)
      setLineErr(lr.e)
    }
    if (rr.ok) setResolutionData(rr.d)
    else {
      setResolutionData(null)
      setResolutionErr(rr.e)
    }
    if (cr.ok) setCrossData(cr.d)
    else {
      setCrossData(null)
      setCrossErr(cr.e)
    }
    setLoading(false)
  }

  useEffect(() => {
    load()
  }, [])

  const ld = lineData
  const rd = resolutionData
  const cd = crossData

  const resolutionBarData =
    rd?.issue_type_summary?.map((d) => ({
      name: d.display_name,
      hours: d.avg_resolution_hours,
      slow: d.status === 'slow',
    })) || []

  const maxHours = Math.max(0.001, ...resolutionBarData.map((d) => Number(d.hours) || 0))

  const attrData = cd?.delay_attribution ? Object.entries(cd.delay_attribution).map(([name, pct]) => ({ name, pct })) : []

  return (
    <div className="relos-page">
      <h2>
        产线效率与运营分析 <span className="badge b-blue">S-07 / S-08 / S-09</span>
      </h2>
      <div className="muted mb12" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <span>产线效率 · 跨部门协同 · 异常处理</span>
        <button type="button" className="btn btn-sm" onClick={load} disabled={loading}>
          <RefreshCw className={loading ? 'relos-icon-spin' : ''} style={{ width: 14, height: 14 }} />
          刷新
        </button>
      </div>

      <div className="card mb12" style={{ background: 'var(--blue-l)', borderColor: 'var(--blue)' }}>
        <span style={{ fontSize: 12, color: 'var(--blue-ink)' }}>
          演示数据请运行 <code style={{ fontSize: 11 }}>python scripts/seed_neo4j.py</code> 后执行{' '}
          <code style={{ fontSize: 11 }}>python scripts/seed_demo_scenarios.py</code>。
        </span>
      </div>

      <div className="card mb12">
        <h3>产线效率看板（S-07）</h3>
        {loading ? (
          <p className="muted mt8">加载中…</p>
        ) : lineErr ? (
          <p className="muted mt8" style={{ color: 'var(--red)' }}>
            {lineErr}
          </p>
        ) : !ld?.lines?.length ? (
          <p className="muted mt8">暂无产线数据（图谱中缺少场景 7 所需节点与关系）。</p>
        ) : (
          <div className="mt8">
            {ld.lines.map((line) => {
              const isBottleneck = line.line_id === ld.bottleneck_line_id || line.status === 'bottleneck'
              return (
                <LineBar
                  key={line.line_id}
                  line={line}
                  isBottleneck={isBottleneck}
                  expanded={expandedLine === line.line_id}
                  rootPath={ld.root_cause_path}
                  contributionPct={ld.bottleneck_contribution_pct}
                  onClick={() =>
                    setExpandedLine(
                      isBottleneck ? (expandedLine === line.line_id ? null : line.line_id) : null
                    )
                  }
                />
              )
            })}
          </div>
        )}
      </div>

      <div className="g2">
        <div className="card">
          <h3>异常处理效率（S-09）</h3>
          {loading ? (
            <p className="muted mt8">加载中…</p>
          ) : resolutionErr ? (
            <p className="muted mt8" style={{ color: 'var(--red)' }}>
              {resolutionErr}
            </p>
          ) : resolutionBarData.length === 0 ? (
            <p className="muted mt8">暂无异常处理统计数据。</p>
          ) : (
            <>
              <p className="muted" style={{ fontSize: 11, marginTop: 4 }}>
                平均处理时长（与原型「来源分布」相同的 cbar 行）
              </p>
              <div className="mt8">
                {resolutionBarData.map((entry) => (
                  <div key={entry.name} className="rrow" style={{ flexWrap: 'wrap' }}>
                    <span className="rnode" style={{ maxWidth: '42%', fontSize: 11 }}>
                      {entry.name}
                    </span>
                    <div className="cbar" style={{ flex: 1, minWidth: 100 }}>
                      <div
                        className={`cfill ${entry.slow ? 'cf-low' : 'cf-high'}`}
                        style={{ width: `${(Number(entry.hours) / maxHours) * 100}%` }}
                      />
                    </div>
                    <span className="badge" style={{ fontSize: 10, background: entry.slow ? 'var(--red-l)' : 'var(--green-l)', color: entry.slow ? 'var(--red)' : 'var(--green)' }}>
                      {entry.hours}h
                    </span>
                  </div>
                ))}
              </div>

              {rd.shift_comparison && (
                <div className="ann-src mt8">
                  <p className="muted" style={{ fontSize: 11, marginBottom: 6 }}>
                    班次对比
                  </p>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                    <div>
                      <p className="muted" style={{ fontSize: 10 }}>
                        夜班
                      </p>
                      <p style={{ fontWeight: 600, color: 'var(--red)' }}>{rd.shift_comparison.night_avg_hours}h</p>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <p className="muted" style={{ fontSize: 10 }}>
                        慢
                      </p>
                      <p style={{ fontWeight: 600, color: 'var(--amber)' }}>{rd.shift_comparison.night_vs_day_ratio}×</p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <p className="muted" style={{ fontSize: 10 }}>
                        白班
                      </p>
                      <p style={{ fontWeight: 600, color: 'var(--green)' }}>{rd.shift_comparison.day_avg_hours}h</p>
                    </div>
                  </div>
                </div>
              )}

              {rd.insight && (
                <p className="muted" style={{ fontSize: 11, fontStyle: 'italic', marginTop: 10, marginBottom: 0 }}>
                  {rd.insight}
                </p>
              )}
            </>
          )}
        </div>

        <div className="card">
          <h3>跨部门协同（S-08）</h3>
          {loading ? (
            <p className="muted mt8">加载中…</p>
          ) : crossErr ? (
            <p className="muted mt8" style={{ color: 'var(--red)' }}>
              {crossErr}
            </p>
          ) : !cd?.causal_chain?.length && attrData.length === 0 ? (
            <p className="muted mt8">暂无跨部门分析数据。</p>
          ) : (
            <>
              <div style={{ marginBottom: 12 }}>
                {cd.causal_chain?.map((step, i) => (
                  <div key={i} className="tl-item">
                    <span className="tl-dot" />
                    <span style={{ fontSize: 12, color: 'var(--t1)', lineHeight: 1.5 }}>{step}</span>
                  </div>
                ))}
              </div>

              {attrData.length > 0 && (
                <div>
                  <h3 style={{ marginTop: 12 }}>延误责任分布</h3>
                  <div className="mt8">
                    {attrData.map(({ name, pct }) => (
                      <div key={name} className="rrow" style={{ flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 12, minWidth: 72 }}>{name}</span>
                        <div className="cbar" style={{ flex: 1, minWidth: 80 }}>
                          <div className="cfill cf-mid" style={{ width: `${Math.min(100, pct)}%` }} />
                        </div>
                        <span className="badge b-amber">{pct}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {cd.total_delay_days != null && (
                <p className="muted" style={{ fontSize: 11, marginTop: 8, marginBottom: 0 }}>
                  总延误影响：<strong style={{ color: 'var(--amber)' }}>{cd.total_delay_days} 天</strong>
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
