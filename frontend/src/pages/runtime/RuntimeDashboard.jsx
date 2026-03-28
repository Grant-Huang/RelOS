/**
 * 运行时仪表盘：指标来自 GET /v1/metrics，事件流来自 GET /v1/telemetry/runtime-feed
 */
import { useCallback, useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { getMetrics, getRuntimeFeed } from '../../api/client'

function toastColor(hex) {
  if (hex === '#3B6D11') return 'var(--green)'
  if (hex === '#A32D2D') return 'var(--red)'
  return 'var(--blue)'
}

function EvRow({ ev }) {
  const typeLabel =
    ev.timeLineLabel ??
    (ev.type === 'auto' ? '自动标注' : ev.type === 'prompt' ? '待确认' : '新事件')
  const cf = ev.c >= 0.8 ? 'cf-high' : ev.c >= 0.65 ? 'cf-mid' : 'cf-low'
  const rel = ev.rel || { f: '—', r: '—', t: '—' }
  return (
    <div className={`ev-item ev-${ev.type || 'auto'}`}>
      <div className="ev-time">
        {ev.ts} · {typeLabel}
      </div>
      <div className="ev-title">{ev.label}</div>
      <div className="ev-rel">
        <span className="rnode">{rel.f}</span>
        <span style={{ fontSize: 10, color: 'var(--t2)' }}>→ {rel.r} →</span>
        <span className="rnode">{rel.t}</span>
        {ev.compact ? (
          <span className={`badge ${ev.c >= 0.8 ? 'b-green' : 'b-amber'}`} style={{ fontSize: 9 }}>
            {Number(ev.c).toFixed(2)}
          </span>
        ) : (
          <>
            <div className="cbar" style={{ maxWidth: 50 }}>
              <div className={`cfill ${cf}`} style={{ width: `${Number(ev.c) * 100}%` }} />
            </div>
            <span style={{ fontSize: 10, fontWeight: 500 }}>{Number(ev.c).toFixed(2)}</span>
            {ev.type === 'auto' ? (
              <span className="badge b-green" style={{ fontSize: 9 }}>
                自动写入
              </span>
            ) : (
              <span className="badge b-amber" style={{ fontSize: 9 }}>
                待确认
              </span>
            )}
          </>
        )}
      </div>
    </div>
  )
}

const PROV_LABEL = {
  sensor_realtime: 'IoT 自动抽取',
  llm_extracted: 'LLM / 文档抽取',
  manual_engineer: '专家手动输入',
  mes_structured: 'MES 结构化',
  inference: '系统推断',
  structured_document: '企业文档',
  expert_document: '专家文档',
  unknown: '其他',
}

export default function RuntimeDashboard() {
  const [events, setEvents] = useState([])
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [feedErr, setFeedErr] = useState(null)
  const [notif, setNotif] = useState(null)

  const toast = useCallback((msg, color = '#185FA5') => {
    setNotif({ msg, color: toastColor(color) })
    window.setTimeout(() => setNotif(null), 2500)
  }, [])

  const refresh = useCallback(async () => {
    setLoading(true)
    setFeedErr(null)
    try {
      const [m, feed] = await Promise.all([
        getMetrics().catch(() => null),
        getRuntimeFeed(12).catch((e) => {
          setFeedErr(e.message || '事件流加载失败')
          return []
        }),
      ])
      setMetrics(m)
      const list = Array.isArray(feed) ? feed : []
      setEvents(
        list.map((ev) => ({
          ...ev,
          compact: true,
          timeLineLabel: ev.type === 'auto' ? '自动标注' : '待确认',
        })),
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const totalRel = metrics?.total_relations ?? 0
  const pending = metrics?.pending_review_count ?? 0
  const provRows = metrics?.provenance_breakdown || []
  const maxProv = Math.max(1, ...provRows.map((p) => p.count))

  return (
    <div className="relos-page">
      <div
        className={`relos-notif${notif ? ' on' : ''}`}
        style={notif ? { background: notif.color } : undefined}
      >
        {notif?.msg}
      </div>

      <h2>
        运行时仪表盘 <span className="badge b-blue">用户前端 · 操作员视角</span>
      </h2>

      <div className="muted mb12" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span>指标与事件流来自后端 API；埋点为内存存储，重启后清空。</span>
        <button type="button" className="btn btn-sm" onClick={refresh} disabled={loading}>
          <RefreshCw className={loading ? 'relos-icon-spin' : ''} style={{ width: 12, height: 12 }} />
          刷新
        </button>
      </div>

      <div className="g4 mb12">
        <div className="stat">
          <div className="stat-v" style={{ color: 'var(--t3)' }}>—</div>
          <div className="stat-l">今日已处理报警（待对接业务 API）</div>
        </div>
        <div className="stat">
          <div className="stat-v" style={{ color: 'var(--t3)' }}>—</div>
          <div className="stat-l">自动标注命中率（待对接）</div>
        </div>
        <div className="stat">
          <div className="stat-v" style={{ color: 'var(--amber)' }}>
            {loading ? '…' : pending}
          </div>
          <div className="stat-l">待人工确认（pending_review）</div>
        </div>
        <div className="stat">
          <div className="stat-v" style={{ color: 'var(--t1)' }}>
            {loading ? '…' : totalRel.toLocaleString('zh-CN')}
          </div>
          <div className="stat-l">图谱关系总数</div>
        </div>
      </div>

      <div className="g2">
        <div className="card">
          <h3>
            实时事件流{' '}
            <span className="badge b-gray" style={{ fontSize: 10 }}>
              埋点
            </span>
          </h3>
          {feedErr ? <p className="muted" style={{ color: 'var(--red)', fontSize: 12 }}>{feedErr}</p> : null}
          {!loading && !feedErr && events.length === 0 ? (
            <p className="muted" style={{ fontSize: 12 }}>
              暂无埋点事件。使用告警分析等功能会产生遥测并显示于此。
            </p>
          ) : null}
          <div>
            {events.map((ev, i) => (
              <EvRow key={`${ev.ts}-${ev.label}-${i}`} ev={ev} />
            ))}
          </div>
        </div>

        <div className="card">
          <h3>当前活跃决策建议</h3>
          <p className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
            聚合决策流尚未提供独立 API；请使用 <strong>告警分析</strong> 或 <strong>提示标注</strong> 完成闭环操作。
          </p>
          <button type="button" className="btn btn-sm" onClick={() => toast('请从侧边栏进入「告警根因分析」或「提示标注工作区」', '#185FA5')}>
            查看引导
          </button>
        </div>
      </div>

      <div className="card mt10">
        <h3>关系来源分布（图谱）</h3>
        {!metrics?.provenance_breakdown?.length ? (
          <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>暂无数据或尚未加载 metrics。</p>
        ) : (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
            {provRows.slice(0, 6).map((p) => {
              const label = PROV_LABEL[p.provenance] || p.provenance
              const pct = Math.round((p.count / maxProv) * 100)
              return (
                <div key={p.provenance} style={{ flex: 1, minWidth: 120 }}>
                  <div style={{ fontSize: 11, color: 'var(--t2)', marginBottom: 4 }}>{label}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div className="cbar">
                      <div className="cfill cf-mid" style={{ width: `${pct}%` }} />
                    </div>
                    <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--t1)' }}>{p.count}</span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
