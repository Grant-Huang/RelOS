/**
 * 自动标注监控：透明度 —— 系统背后自动做了什么（首版：埋点 + 规则说明）
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { RefreshCw, Info } from 'lucide-react'
import { listTelemetryEvents } from '../../api/client'

const MOCK_EVENTS = [
  {
    event_id: 'mock-1',
    timestamp: new Date().toISOString(),
    event_name: 'recommendation_shown',
    confidence_trace_id: 'conf-trace-demo',
    props: { engine_used: 'rule_engine', confidence: 0.85 },
  },
]

function formatTime(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

export default function AutomationMonitor() {
  const navigate = useNavigate()
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [usedMock, setUsedMock] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const data = await listTelemetryEvents(80)
      const list = Array.isArray(data) ? data : []
      if (list.length === 0) {
        setEvents(MOCK_EVENTS)
        setUsedMock(true)
      } else {
        setEvents(list)
        setUsedMock(false)
      }
    } catch {
      setEvents(MOCK_EVENTS)
      setUsedMock(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h1 className="text-xl md:text-2xl font-semibold" style={{ color: 'var(--wb-text)' }}>
            自动标注监控
          </h1>
          <p className="text-sm wb-text-muted mt-1">
            高置信度自动写入由策略控制；此处展示近期系统事件流（含埋点），便于追溯。
          </p>
        </div>
        <button type="button" onClick={load} disabled={loading} className="wb-btn-ghost flex items-center gap-2 min-h-[44px]">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      <div className="wb-card p-4 mb-6">
        <div className="flex items-start gap-2 mb-3">
          <Info className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: 'var(--wb-blue)' }} />
          <div className="text-sm wb-text-secondary space-y-1">
            <p>
              <strong>规则（产品约定）</strong>：置信度 ≥ 0.80 的自动写入可在策略中开启；0.50–0.79 进入
              <button type="button" className="underline mx-1" onClick={() => navigate('/runtime/prompt')}>
                提示标注工作区
              </button>
              。
            </p>
            <p className="text-xs wb-text-muted">后续可接入专用自动标注日志 API 或 SSE。</p>
          </div>
        </div>
      </div>

      {usedMock && (
        <p className="text-sm wb-text-muted mb-3">当前为演示数据或后端无埋点记录；接入后端后会显示真实事件。</p>
      )}

      <h2 className="text-sm font-medium wb-text-secondary mb-2">事件时间线</h2>
      <div className="space-y-2">
        {loading ? (
          <div className="wb-card p-8 wb-text-muted text-center">加载中…</div>
        ) : events.length === 0 ? (
          <div className="wb-card p-8 wb-text-muted text-center">暂无事件</div>
        ) : (
          events.map((ev, i) => {
            const name = ev.event_name || 'event'
            const auto = name.includes('recommendation') || name.includes('auto')
            const cls = auto ? 'wb-event-auto' : name.includes('prompt') || name.includes('interview') ? 'wb-event-prompt' : 'wb-event-info'
            return (
              <div key={ev.event_id || i} className={`wb-card p-3 pl-3 ${cls}`}>
                <p className="text-[10px] wb-text-muted">{formatTime(ev.timestamp)}</p>
                <p className="text-sm font-medium" style={{ color: 'var(--wb-text)' }}>
                  {name}
                </p>
                {ev.confidence_trace_id && (
                  <p className="text-xs wb-text-muted mt-1 font-mono">trace: {ev.confidence_trace_id}</p>
                )}
                {ev.props && Object.keys(ev.props).length > 0 && (
                  <pre className="text-[11px] wb-text-muted mt-2 overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(ev.props, null, 0)}
                  </pre>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
