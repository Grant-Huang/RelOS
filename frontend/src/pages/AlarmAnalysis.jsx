/**
 * AlarmAnalysis — 告警根因分析页（场景 S-01）
 * 工程师输入告警码 → 获取 AI 根因推荐 → 确认/否定反馈
 */
import { useState } from 'react'
import { Bell, Search, ChevronRight } from 'lucide-react'
import AlarmRootCauseCard from '../components/AlarmRootCauseCard'
import { analyzeAlarm } from '../api/client'

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
    try {
      const data = await analyzeAlarm({
        alarm_id: `alarm-${form.alarm_code}`,
        device_id: form.device_id,
        alarm_code: form.alarm_code,
        alarm_description: form.alarm_description,
      })
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const extractResult = (data) => {
    // 兼容后端不同响应结构
    const rec = data?.recommendation || data?.root_cause_recommendation || data
    return {
      recommendedCause: rec?.recommended_cause || rec?.root_cause || '未能确定根因',
      confidence: rec?.confidence ?? rec?.confidence_score ?? 0,
      engineUsed: rec?.engine_used || 'rule_engine',
      shadowMode: rec?.shadow_mode ?? true,
      supportingRelations: rec?.supporting_relations || [],
    }
  }

  const resultData = result ? extractResult(result) : null

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
        </div>
      )}
    </div>
  )
}
