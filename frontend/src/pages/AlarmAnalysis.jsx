/**
 * 告警根因分析（场景 S-01）— 使用全局 .relos-page / .card / .btn / .muted
 */
import { useState, useEffect } from 'react'
import { Search } from 'lucide-react'
import AlarmRootCauseCard from '../components/AlarmRootCauseCard'
import { analyzeAlarmStream, postTelemetryEvent, streamAnswer, getQuickAlarmsConfig } from '../api/client'

export default function AlarmAnalysis() {
  const [form, setForm] = useState({
    alarm_code: '',
    device_id: '',
    device_name: '',
    alarm_description: '',
  })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stream, setStream] = useState({
    summary: null,
    evidence: [],
    contributions: [],
    question: null,
    traceId: '',
  })
  const [answering, setAnswering] = useState(false)
  const [quickAlarms, setQuickAlarms] = useState([])

  useEffect(() => {
    let cancelled = false
    getQuickAlarmsConfig()
      .then((items) => {
        if (!cancelled && Array.isArray(items)) setQuickAlarms(items)
      })
      .catch(() => {
        if (!cancelled) setQuickAlarms([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleQuick = (q) => {
    setForm({
      alarm_code: q.code,
      device_id: q.device,
      device_name: q.name,
      alarm_description: q.desc,
    })
    setResult(null)
    setError(null)
  }

  const handleAnalyze = async () => {
    if (!form.alarm_code || !form.device_id) return
    setLoading(true)
    setResult(null)
    setError(null)
    setStream({ summary: null, evidence: [], contributions: [], question: null, traceId: '' })
    try {
      await analyzeAlarmStream(
        {
          alarm_id: `alarm-${form.alarm_code}`,
          device_id: form.device_id,
          alarm_code: form.alarm_code,
          alarm_description: form.alarm_description,
        },
        (evt, data) => {
          if (evt === 'summary') {
            setStream((s) => ({ ...s, summary: data, traceId: data.confidence_trace_id || s.traceId }))
            postTelemetryEvent({
              event_name: 'recommendation_shown',
              confidence_trace_id: data.confidence_trace_id,
              alarm_id: `alarm-${form.alarm_code}`,
              device_id: form.device_id,
              props: {
                engine_used: data.engine_used,
                confidence: data.confidence,
              },
            }).catch(() => {})
          }
          if (evt === 'evidence') {
            setStream((s) => ({
              ...s,
              traceId: data.confidence_trace_id || s.traceId,
              evidence: Array.isArray(data.evidence_relations) ? data.evidence_relations : s.evidence,
            }))
          }
          if (evt === 'contributions') {
            setStream((s) => ({
              ...s,
              traceId: data.confidence_trace_id || s.traceId,
              contributions: Array.isArray(data.phase_contributions) ? data.phase_contributions : s.contributions,
            }))
          }
          if (evt === 'question') {
            setStream((s) => ({ ...s, question: data.question || null, traceId: data.confidence_trace_id || s.traceId }))
          }
          if (evt === 'done') {
            setResult({ done: true })
          }
        }
      )
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const resultData = stream?.summary
    ? {
        recommendedCause: stream.summary.recommended_cause || '未能确定根因',
        confidence: stream.summary.confidence ?? 0,
        engineUsed: stream.summary.engine_used || 'rule_engine',
        shadowMode: stream.summary.shadow_mode ?? true,
        supportingRelations: stream.evidence || [],
      }
    : null

  const handleAnswer = async (answer) => {
    if (!stream.traceId || !stream.question?.question_id) return
    setAnswering(true)
    try {
      await streamAnswer({
        confidence_trace_id: stream.traceId,
        question_id: stream.question.question_id,
        answer,
      })
      postTelemetryEvent({
        event_name: 'stream_question_answered',
        confidence_trace_id: stream.traceId,
        alarm_id: `alarm-${form.alarm_code}`,
        device_id: form.device_id,
        props: { question_id: stream.question.question_id, answer },
      }).catch(() => {})
    } catch (e) {
      setError(e.message)
    } finally {
      setAnswering(false)
    }
  }

  return (
    <div className="relos-page">
      <h2>
        告警根因分析 <span className="badge b-red">场景 S-01</span>
      </h2>
      <div className="muted mb12">输入告警信息，获取 AI 根因推荐与流式解释</div>

      <div className="card mb12">
        <h3>演示告警 · 快速选择</h3>
        <div className="muted" style={{ marginBottom: 8, fontSize: 11 }}>
          与「专家知识 · 选择访谈场景」相同的卡片选中态
        </div>
        <div className="g2" style={{ marginTop: 8 }}>
          {quickAlarms.length === 0 ? (
            <p className="muted" style={{ fontSize: 12 }}>
              未加载到快速选择项。请确认后端可用，且包内存在 relos/demo_data/quick_alarms.json。
            </p>
          ) : null}
          {quickAlarms.map((q) => (
            <div
              key={q.code}
              className="card"
              role="button"
              tabIndex={0}
              onClick={() => handleQuick(q)}
              onKeyDown={(e) => e.key === 'Enter' && handleQuick(q)}
              style={{
                cursor: 'pointer',
                marginBottom: 0,
                padding: '10px 12px',
                border: form.alarm_code === q.code ? '1.5px solid var(--blue)' : '0.5px solid var(--b1)',
                background: form.alarm_code === q.code ? 'var(--blue-l)' : 'var(--bg)',
                transition: 'border-color 0.15s',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span className="badge b-red">{q.code}</span>
                <span className="muted" style={{ fontSize: 11 }}>
                  {q.desc}
                </span>
              </div>
              <div className="muted" style={{ fontSize: 10, marginTop: 6 }}>
                {q.name}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card mb12">
        <h3>告警信息</h3>
        <div className="g2 mt8">
          <div>
            <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>
              告警码 *
            </div>
            <input
              type="text"
              value={form.alarm_code}
              onChange={(e) => setForm({ ...form, alarm_code: e.target.value })}
              placeholder="如 VIB-001"
            />
          </div>
          <div>
            <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>
              设备 ID *
            </div>
            <input
              type="text"
              value={form.device_id}
              onChange={(e) => setForm({ ...form, device_id: e.target.value })}
              placeholder="如 device-M1"
            />
          </div>
          <div>
            <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>
              设备名称
            </div>
            <input
              type="text"
              value={form.device_name}
              onChange={(e) => setForm({ ...form, device_name: e.target.value })}
              placeholder="如 1号机（注塑机）"
            />
          </div>
          <div>
            <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>
              告警描述
            </div>
            <input
              type="text"
              value={form.alarm_description}
              onChange={(e) => setForm({ ...form, alarm_description: e.target.value })}
              placeholder="如 振动超限"
            />
          </div>
        </div>

        <button
          type="button"
          className="btn btn-p mt-3 w-full justify-center disabled:cursor-not-allowed disabled:opacity-40"
          onClick={handleAnalyze}
          disabled={loading || !form.alarm_code || !form.device_id}
        >
          {loading ? (
            <>正在分析关系图谱…</>
          ) : (
            <>
              <Search style={{ width: 16, height: 16 }} />
              分析告警根因
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="card mb12" style={{ borderColor: 'var(--red)', background: 'var(--red-l)' }}>
          <p style={{ fontWeight: 500, color: 'var(--red)', marginBottom: 4 }}>分析失败</p>
          <p className="muted" style={{ color: 'var(--red)', margin: 0 }}>
            {error}
          </p>
        </div>
      )}

      {resultData && (
        <div className="mb12">
          <h3>分析结果</h3>
          <div style={{ marginTop: 10 }}>
            <AlarmRootCauseCard
              alarmCode={form.alarm_code}
              deviceName={form.device_name || form.device_id}
              recommendedCause={resultData.recommendedCause}
              confidence={resultData.confidence}
              engineUsed={resultData.engineUsed}
              shadowMode={resultData.shadowMode}
              supportingRelations={resultData.supportingRelations}
              onConfirm={() => {}}
              onReject={() => {}}
            />
          </div>

          {stream.question && (
            <div className="qcard" style={{ marginTop: 12 }}>
              <div className="q-num">流式澄清问题</div>
              <div className="q-text">{stream.question.prompt}</div>
              <div className="ann-actions" style={{ marginTop: 0 }}>
                {(stream.question.options || []).map((opt, i) => (
                  <button
                    key={opt.id}
                    type="button"
                    className={i === 0 ? 'btn btn-p btn-sm' : 'btn btn-sm'}
                    disabled={answering}
                    onClick={() => handleAnswer(opt.id)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <p className="muted" style={{ fontSize: 10, marginTop: 10, marginBottom: 0 }}>
                trace：<span style={{ fontFamily: 'ui-monospace, monospace' }}>{stream.traceId || '—'}</span>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
