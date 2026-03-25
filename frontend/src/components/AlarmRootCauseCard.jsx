/**
 * AlarmRootCauseCard — 告警根因分析卡片
 * 包含：设备信息、推荐根因、置信度、依据关系（可折叠）、操作区
 */
import { useState } from 'react'
import { ChevronDown, ChevronUp, AlertTriangle, Cpu, CheckCircle, XCircle } from 'lucide-react'
import ConfidenceBar from './ConfidenceBar'

const ENGINE_LABELS = {
  rule_engine: '规则引擎',
  llm: 'AI 分析',
  hitl: '人工审核',
}

const ENGINE_COLORS = {
  rule_engine: 'text-green-400',
  llm: 'text-blue-400',
  hitl: 'text-yellow-400',
}

export default function AlarmRootCauseCard({
  alarmCode,
  deviceName,
  recommendedCause,
  confidence,
  engineUsed = 'rule_engine',
  shadowMode = true,
  supportingRelations = [],
  onConfirm,
  onReject,
  loading = false,
}) {
  const [expanded, setExpanded] = useState(false)
  const [feedback, setFeedback] = useState(null) // 'confirmed' | 'rejected'

  const handleConfirm = () => {
    setFeedback('confirmed')
    onConfirm?.()
  }

  const handleReject = () => {
    setFeedback('rejected')
    onReject?.()
  }

  if (feedback) {
    return (
      <div className="bg-surface rounded-xl p-6 border border-gray-700">
        <div className="flex flex-col items-center gap-3 py-4">
          {feedback === 'confirmed' ? (
            <>
              <CheckCircle className="w-12 h-12 text-confidence-high" />
              <p className="text-lg font-semibold text-confidence-high">反馈已提交</p>
              <p className="text-gray-400 text-sm text-center">
                系统已学习这条经验，置信度将随反馈持续优化
              </p>
            </>
          ) : (
            <>
              <XCircle className="w-12 h-12 text-confidence-low" />
              <p className="text-lg font-semibold text-confidence-low">已标记为不适用</p>
              <p className="text-gray-400 text-sm text-center">
                感谢反馈，系统将调低此推荐的置信度
              </p>
            </>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-surface rounded-xl border border-gray-700 overflow-hidden">
      {/* 头部：设备信息 */}
      <div className="px-6 py-4 border-b border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Cpu className="w-5 h-5 text-gray-400" />
          <div>
            <p className="font-semibold text-white">{deviceName}</p>
            <p className="text-sm text-gray-400 font-mono">{alarmCode}</p>
          </div>
        </div>
        <span className="flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full bg-red-900/40 text-red-400 border border-red-800">
          <AlertTriangle className="w-3.5 h-3.5" />
          告警触发
        </span>
      </div>

      {/* 主体：推荐根因 + 置信度 */}
      <div className="px-6 py-5">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">推荐根因</p>
        <p className="text-2xl font-bold text-white mb-4">{recommendedCause}</p>
        <ConfidenceBar value={confidence} size="md" />

        <div className="mt-4 flex gap-6 text-sm text-gray-400">
          <span>
            引擎：
            <span className={`font-medium ${ENGINE_COLORS[engineUsed] || 'text-gray-300'}`}>
              {ENGINE_LABELS[engineUsed] || engineUsed}
            </span>
          </span>
        </div>
      </div>

      {/* 可折叠：依据关系 */}
      {supportingRelations.length > 0 && (
        <div className="border-t border-gray-700">
          <button
            className="w-full px-6 py-3 flex items-center justify-between text-sm text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
            onClick={() => setExpanded(!expanded)}
          >
            <span>查看依据关系（{supportingRelations.length} 条）</span>
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {expanded && (
            <div className="px-6 pb-4 space-y-3">
              {supportingRelations.map((rel, i) => (
                <div key={i} className="bg-bg rounded-lg p-3 border border-gray-800">
                  <p className="font-mono text-xs text-blue-400 mb-1">{rel.relation_type}</p>
                  <p className="text-sm text-gray-200">
                    {rel.source_node_id} → {rel.target_node_id}
                  </p>
                  {rel.notes && (
                    <p className="text-xs text-gray-500 mt-1 italic">"{rel.notes}"</p>
                  )}
                  <div className="mt-2">
                    <ConfidenceBar value={rel.confidence} size="sm" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Shadow Mode 提示 */}
      {shadowMode && (
        <div className="mx-6 mb-4 rounded-lg bg-orange-900/30 border border-orange-800 px-4 py-2.5 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-orange-400 flex-shrink-0" />
          <p className="text-sm text-orange-300">
            Shadow Mode 开启 · 建议已记录，未自动下发工单
          </p>
        </div>
      )}

      {/* 操作区 */}
      <div className="px-6 pb-6 grid grid-cols-2 gap-3">
        <button
          onClick={handleConfirm}
          disabled={loading}
          className="flex items-center justify-center gap-2 py-3 rounded-lg bg-confidence-high hover:bg-green-500 disabled:opacity-50 transition-colors font-semibold text-white text-base"
        >
          <CheckCircle className="w-5 h-5" />
          确认根因
        </button>
        <button
          onClick={handleReject}
          disabled={loading}
          className="flex items-center justify-center gap-2 py-3 rounded-lg bg-confidence-low hover:bg-red-500 disabled:opacity-50 transition-colors font-semibold text-white text-base"
        >
          <XCircle className="w-5 h-5" />
          不是这个
        </button>
      </div>
    </div>
  )
}
