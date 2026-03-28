/**
 * Interview — 阶段2：访谈微卡片（类流式）
 */
import { useEffect, useState } from 'react'
import { ClipboardCheck, ChevronRight, Loader2 } from 'lucide-react'
import { createInterviewSession, getInterviewNextCard, postTelemetryEvent, submitInterviewCard } from '../api/client'

export default function Interview({ embedded = false }) {
  const [sessionId, setSessionId] = useState('')
  const [engineerId, setEngineerId] = useState('eng-1')
  const [loading, setLoading] = useState(false)
  const [card, setCard] = useState(null)
  const [error, setError] = useState(null)

  const start = async () => {
    setLoading(true)
    setError(null)
    try {
      const s = await createInterviewSession({ engineer_id: engineerId, limit: 20 })
      setSessionId(s.session_id)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const loadNext = async (sid) => {
    setLoading(true)
    setError(null)
    try {
      const res = await getInterviewNextCard(sid)
      setCard(res.card)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (sessionId) loadNext(sessionId)
  }, [sessionId])

  const act = async (action) => {
    if (!sessionId || !card) return
    setLoading(true)
    setError(null)
    try {
      await submitInterviewCard(sessionId, {
        card_id: card.card_id,
        action,
        relation_id: card?.relation?.id,
      })
      postTelemetryEvent({
        event_name: 'expert_interview_task_completed',
        props: { task_type: 'relation_confirm', result: action, relation_id: card?.relation?.id },
      }).catch(() => {})
      await loadNext(sessionId)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={embedded ? 'max-w-3xl mx-auto' : 'p-8 max-w-3xl mx-auto'}>
      {!embedded && (
        <div className="flex items-center gap-3 mb-8">
          <ClipboardCheck className="w-6 h-6 text-yellow-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">访谈微卡片</h1>
            <p className="text-gray-500 text-sm">阶段 2 · 微任务卡片（confirm / reject / unsure）</p>
          </div>
        </div>
      )}

      <div className="bg-surface rounded-xl border border-gray-700 p-6 mb-6">
        <p className="text-sm font-medium text-gray-400 mb-4">会话</p>
        <div className="flex flex-col md:flex-row gap-3">
          <input
            value={engineerId}
            onChange={(e) => setEngineerId(e.target.value)}
            className="flex-1 bg-bg border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-600"
            placeholder="engineer_id"
          />
          <button
            onClick={start}
            disabled={loading}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white font-semibold"
          >
            开始访谈
          </button>
        </div>
        {sessionId && (
          <p className="text-xs text-gray-600 mt-3">
            session：<span className="font-mono">{sessionId}</span>
          </p>
        )}
      </div>

      {error && (
        <div className="mb-6 bg-red-900/30 border border-red-800 rounded-xl px-5 py-4">
          <p className="text-red-300 font-medium">操作失败</p>
          <p className="text-red-500 text-sm mt-1">{error}</p>
        </div>
      )}

      {sessionId && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <ChevronRight className="w-4 h-4 text-gray-500" />
            <p className="text-sm text-gray-400">当前卡片</p>
          </div>

          <div className="bg-surface rounded-xl border border-gray-700 p-6">
            {loading && (
              <div className="flex items-center gap-2 text-gray-400 text-sm">
                <Loader2 className="w-4 h-4 animate-spin" />
                加载中...
              </div>
            )}

            {!loading && card?.type === 'done' && (
              <p className="text-gray-300">{card.message}</p>
            )}

            {!loading && card?.type === 'relation_confirm' && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider">关系确认卡</p>
                <p className="text-white font-medium mt-2">{card.hint}</p>
                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="rounded-lg border border-gray-700 bg-bg p-4">
                    <p className="text-xs text-gray-500">relation_type</p>
                    <p className="font-mono text-sm text-white mt-1">{card.relation.relation_type}</p>
                    <p className="text-xs text-gray-500 mt-3">source → target</p>
                    <p className="text-sm text-gray-200 mt-1">
                      {card.relation.source_node_id} → {card.relation.target_node_id}
                    </p>
                    <p className="text-xs text-gray-500 mt-3">confidence / status</p>
                    <p className="text-sm text-gray-200 mt-1">
                      {card.relation.confidence} · {card.relation.status}
                    </p>
                  </div>
                  <div className="rounded-lg border border-gray-700 bg-bg p-4">
                    <p className="text-xs text-gray-500">provenance</p>
                    <p className="text-sm text-gray-200 mt-1">{card.relation.provenance}</p>
                    <p className="text-xs text-gray-500 mt-3">detail</p>
                    <p className="text-sm text-gray-200 mt-1">{card.relation.provenance_detail || '—'}</p>
                  </div>
                </div>

                <div className="mt-5 flex flex-col md:flex-row gap-3">
                  <button
                    onClick={() => act('confirm')}
                    disabled={loading}
                    className="flex-1 py-3 rounded-lg bg-confidence-high hover:opacity-90 disabled:opacity-40 text-white font-semibold"
                  >
                    ✓ 确认
                  </button>
                  <button
                    onClick={() => act('reject')}
                    disabled={loading}
                    className="flex-1 py-3 rounded-lg bg-confidence-low hover:opacity-90 disabled:opacity-40 text-white font-semibold"
                  >
                    ✗ 否定
                  </button>
                  <button
                    onClick={() => act('unsure')}
                    disabled={loading}
                    className="flex-1 py-3 rounded-lg border border-gray-700 bg-bg hover:border-gray-500 disabled:opacity-40 text-gray-200 font-semibold"
                  >
                    ? 不确定
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

