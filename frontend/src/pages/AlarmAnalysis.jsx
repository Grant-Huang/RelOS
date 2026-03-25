/**
 * AlarmAnalysis — 告警根因分析页（场景 S-01）
 * 工程师输入告警码 → 获取 AI 根因推荐 → 确认/否定反馈
 */
import { useState } from 'react'
import { Bell, Search, ChevronRight } from 'lucide-react'
import AlarmRootCauseCard from '../components/AlarmRootCauseCard'
import { analyzeAlarmStream, postTelemetryEvent, streamAnswer } from '../api/client'

const QUICK_ALARMS = [
  { code: 'VIB-001', device: 'device-M1', name: '1号机（注塑机）', desc: '振动超限' },
  { code: 'TEMP-002', device: 'device-M2', name: '2号机（焊接机）', desc: '温度异常' },
  { code: 'WELD-003', device: 'device-M3', name: '3号机（M3）', desc: '焊接过热告警' },
]

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
    <div className="p-8 max-w-3xl mx-auto">
      {/* 页头 */}
      <div className="flex items-center gap-3 mb-8">
        <Bell className="w-6 h-6 text-red-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">告警根因分析</h1>
          <p className="text-gray-500 text-sm">场景 S-01 · 输入告警信息，获取 AI 根因推荐</p>
        </div>
      </div>

      {/* 快速选择告警 */}
      <div className="mb-6">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">演示告警 · 快速选择</p>
        <div className="grid grid-cols-3 gap-3">
          {QUICK_ALARMS.map((q) => (
            <button
              key={q.code}
              onClick={() => handleQuick(q)}
              className={`text-left rounded-lg border px-4 py-3 transition-all ${
                form.alarm_code === q.code
                  ? 'border-blue-600 bg-blue-900/30'
                  : 'border-gray-700 bg-surface hover:border-gray-500'
              }`}
            >
              <p className="font-mono text-sm font-semibold text-white">{q.code}</p>
              <p className="text-xs text-gray-400 mt-0.5">{q.desc}</p>
              <p className="text-xs text-gray-600 mt-0.5">{q.name}</p>
            </button>
          ))}
        </div>
      </div>

      {/* 输入表单 */}
      <div className="bg-surface rounded-xl border border-gray-700 p-6 mb-6">
        <p className="text-sm font-medium text-gray-400 mb-4">告警信息</p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">告警码 *</label>
            <input
              type="text"
              value={form.alarm_code}
              onChange={(e) => setForm({ ...form, alarm_code: e.target.value })}
              placeholder="如 VIB-001"
              className="w-full bg-bg border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-600"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">设备 ID *</label>
            <input
              type="text"
              value={form.device_id}
              onChange={(e) => setForm({ ...form, device_id: e.target.value })}
              placeholder="如 device-M1"
              className="w-full bg-bg border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-600"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">设备名称</label>
            <input
              type="text"
              value={form.device_name}
              onChange={(e) => setForm({ ...form, device_name: e.target.value })}
              placeholder="如 1号机（注塑机）"
              className="w-full bg-bg border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-600"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">告警描述</label>
            <input
              type="text"
              value={form.alarm_description}
              onChange={(e) => setForm({ ...form, alarm_description: e.target.value })}
              placeholder="如 振动超限"
              className="w-full bg-bg border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-600"
            />
          </div>
        </div>

        <button
          onClick={handleAnalyze}
          disabled={loading || !form.alarm_code || !form.device_id}
          className="mt-5 w-full flex items-center justify-center gap-2 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-semibold text-white"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              正在分析关系图谱...
            </>
          ) : (
            <>
              <Search className="w-4 h-4" />
              分析告警根因
            </>
          )}
        </button>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-6 bg-red-900/30 border border-red-800 rounded-xl px-5 py-4">
          <p className="text-red-300 font-medium">分析失败</p>
          <p className="text-red-500 text-sm mt-1">{error}</p>
        </div>
      )}

      {/* 结果卡片 */}
      {resultData && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <ChevronRight className="w-4 h-4 text-gray-500" />
            <p className="text-sm text-gray-400">分析结果</p>
          </div>
          <AlarmRootCauseCard
            alarmCode={form.alarm_code}
            deviceName={form.device_name || form.device_id}
            recommendedCause={resultData.recommendedCause}
            confidence={resultData.confidence}
            engineUsed={resultData.engineUsed}
            shadowMode={resultData.shadowMode}
            supportingRelations={resultData.supportingRelations}
            onConfirm={() => console.log('confirmed')}
            onReject={() => console.log('rejected')}
          />

          {/* 流式问答（MVP：单问单答） */}
          {stream.question && (
            <div className="mt-4 bg-surface rounded-xl border border-gray-700 p-5">
              <p className="text-xs text-gray-500 uppercase tracking-wider">流式澄清问题</p>
              <p className="text-white font-medium mt-2">{stream.question.prompt}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {(stream.question.options || []).map((opt) => (
                  <button
                    key={opt.id}
                    disabled={answering}
                    onClick={() => handleAnswer(opt.id)}
                    className="px-3 py-2 rounded-lg border border-gray-700 bg-bg text-sm text-gray-200 hover:border-gray-500 disabled:opacity-40"
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <p className="text-xs text-gray-600 mt-3">
                trace：<span className="font-mono">{stream.traceId || '—'}</span>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
