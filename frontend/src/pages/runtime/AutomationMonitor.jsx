/**
 * 自动标注监控 — 对齐 docs/relos_workbench_v2.html #v-rt-auto
 * 最近自动写入来自 GET /v1/telemetry/events（无匹配事件时为空状态）
 */
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import { listTelemetryEvents } from '../../api/client'

function formatTimeShort(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  } catch {
    return '—'
  }
}

function eventToLogRow(ev) {
  const p = ev.props || {}
  const c = typeof p.confidence === 'number' ? p.confidence : 0.85
  const name = ev.event_name || 'event'
  const src =
    p.engine_used === 'rule_engine'
      ? '规则'
      : name.includes('llm') || name.includes('extract')
        ? 'LLM文档'
        : '埋点'
  return {
    f: p.source_id || p.entity || name.slice(0, 12),
    r: p.relation || '—',
    t: p.target_id || p.result || '—',
    c,
    src,
    ts: formatTimeShort(ev.timestamp),
    key: ev.event_id || `${name}-${ev.timestamp}`,
  }
}

export default function AutomationMonitor() {
  const navigate = useNavigate()
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const data = await listTelemetryEvents(80)
      const list = Array.isArray(data) ? data : []
      setEvents(list)
    } catch {
      setEvents([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const dynamicRows = useMemo(() => {
    const rows = events
      .filter((ev) => {
        const n = (ev.event_name || '').toLowerCase()
        return n.includes('recommendation') || n.includes('auto') || n.includes('relation')
      })
      .slice(0, 12)
      .map(eventToLogRow)
    return rows
  }, [events])

  const logRows = dynamicRows

  return (
    <div className="relos-page">
      <h2>
        自动标注监控 <span className="badge b-green">置信度 ≥ 0.80 自动写入</span>
      </h2>
      <div className="muted mb12">
        以下关系由系统从 IoT 事件 / LLM 抽取自动写入图谱，无需人工干预。实时更新，可追溯。高置信度自动写入策略见下表；0.50–0.79 区间请前往
        <button type="button" className="btn btn-sm" style={{ margin: '0 4px', verticalAlign: 'middle' }} onClick={() => navigate('/runtime/prompt')}>
          提示标注工作区
        </button>
        处理。
      </div>

      <div className="card mb10">
        <h3>自动标注规则配置</h3>
        <table className="tbl mt8">
          <thead>
            <tr>
              <th>来源类型</th>
              <th>置信度阈值</th>
              <th>自动写入</th>
              <th>通知用户</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <span className="badge b-blue">IoT 规则抽取</span>
              </td>
              <td>≥ 0.90</td>
              <td>
                <span className="badge b-green">是</span>
              </td>
              <td>否</td>
              <td>
                <button type="button" className="btn btn-sm">
                  配置
                </button>
              </td>
            </tr>
            <tr>
              <td>
                <span className="badge b-teal">LLM 文档抽取</span>
              </td>
              <td>≥ 0.80</td>
              <td>
                <span className="badge b-green">是</span>
              </td>
              <td>
                <span className="badge b-amber">提醒</span>
              </td>
              <td>
                <button type="button" className="btn btn-sm">
                  配置
                </button>
              </td>
            </tr>
            <tr>
              <td>
                <span className="badge b-purple">LLM 对话抽取</span>
              </td>
              <td>-</td>
              <td>
                <span className="badge b-red">否</span>
              </td>
              <td>
                <span className="badge b-amber">待审批</span>
              </td>
              <td>
                <button type="button" className="btn btn-sm">
                  配置
                </button>
              </td>
            </tr>
            <tr>
              <td>
                <span className="badge b-gray">历史统计</span>
              </td>
              <td>≥ 0.75</td>
              <td>
                <span className="badge b-amber">待确认</span>
              </td>
              <td>
                <span className="badge b-amber">提醒</span>
              </td>
              <td>
                <button type="button" className="btn btn-sm">
                  配置
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="g2">
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <h3 style={{ marginBottom: 0 }}>最近自动写入（高置信度）</h3>
            <button type="button" className="btn btn-sm" onClick={load} disabled={loading} title="刷新埋点">
              <RefreshCw style={{ width: 12, height: 12, opacity: loading ? 0.5 : 1 }} />
            </button>
          </div>
          {!loading && logRows.length === 0 && (
            <p className="muted" style={{ marginBottom: 8, fontSize: 11 }}>
              暂无匹配埋点（事件名需包含 recommendation / auto / relation）。告警分析等页面会产生遥测后可在此查看。
            </p>
          )}
          <div id="auto-log">
            {logRows.map((r) => (
              <div key={r.key || `${r.f}-${r.ts}`} className="rrow">
                <span className="rnode" style={{ fontSize: 10 }}>
                  {r.f}
                </span>
                <span style={{ fontSize: 10, color: 'var(--t2)' }}>→{r.r}→</span>
                <span className="rnode" style={{ fontSize: 10 }}>
                  {r.t}
                </span>
                <div className="cbar" style={{ flex: 1 }}>
                  <div className="cfill cf-high" style={{ width: `${Math.min(100, r.c * 100)}%` }} />
                </div>
                <span style={{ fontSize: 10, color: 'var(--green)', minWidth: 28 }}>{r.c}</span>
                <span className="badge b-gray" style={{ fontSize: 9 }}>
                  {r.src}
                </span>
                <span style={{ fontSize: 10, color: 'var(--t3)' }}>{r.ts}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <h3>自动标注质量追踪</h3>
          <div className="muted" style={{ marginBottom: 8 }}>
            基于用户后续反馈计算
          </div>
          <div className="g2 mt8">
            <div className="stat">
              <div className="stat-v" style={{ color: 'var(--green)' }}>
                94.2%
              </div>
              <div className="stat-l">IoT规则准确率</div>
            </div>
            <div className="stat">
              <div className="stat-v" style={{ color: 'var(--blue)' }}>
                81.7%
              </div>
              <div className="stat-l">LLM文档准确率</div>
            </div>
          </div>
          <div className="div" />
          <div style={{ fontSize: 11, color: 'var(--t2)', lineHeight: 1.7 }}>
            过去 7 天：用户否定了 23 条自动写入关系（占总量 1.8%）
            <br />
            否定最多的关系类型：<span className="badge b-amber">INDICATES</span> 共 14 次
            <br />
            建议降低 INDICATES 类型的自动写入阈值至 0.85
          </div>
        </div>
      </div>
    </div>
  )
}
