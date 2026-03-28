/**
 * Interview — 阶段2：访谈微卡片（类流式）
 * workbench：对齐 relos_workbench_v2 的 card / btn / qcard 风格
 */
import { useEffect, useState } from 'react'
import { ClipboardCheck, ChevronRight, Loader2 } from 'lucide-react'
import { createInterviewSession, getInterviewNextCard, postTelemetryEvent, submitInterviewCard } from '../api/client'

export default function Interview({ embedded = false, workbench = false }) {
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

  if (workbench) {
    return (
      <div className="interview-wb">
        <div className="card mb10">
          <h3>会话</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
            <input type="text" value={engineerId} onChange={(e) => setEngineerId(e.target.value)} placeholder="engineer_id" style={{ flex: 1, minWidth: 160 }} />
            <button type="button" className="btn btn-p" onClick={start} disabled={loading}>
              开始访谈
            </button>
          </div>
          {sessionId ? (
            <p className="muted" style={{ marginTop: 8, fontSize: 11 }}>
              session：<span style={{ fontFamily: 'monospace' }}>{sessionId}</span>
            </p>
          ) : null}
        </div>

        {error ? (
          <div className="card mb10" style={{ borderColor: 'var(--red)', background: 'var(--red-l)' }}>
            <p style={{ color: 'var(--red)', fontWeight: 500, margin: 0 }}>操作失败</p>
            <p className="muted" style={{ margin: '6px 0 0', fontSize: 12 }}>
              {error}
            </p>
          </div>
        ) : null}

        {sessionId ? (
          <div className="qcard">
            <div className="q-num">当前卡片</div>
            {loading ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--t2)', fontSize: 12 }}>
                <Loader2 className="w-4 h-4 animate-spin" />
                加载中...
              </div>
            ) : null}

            {!loading && card?.type === 'done' ? <div className="q-text">{card.message}</div> : null}

            {!loading && card?.type === 'relation_confirm' ? (
              <div>
                <div className="q-text" style={{ marginBottom: 8 }}>
                  {card.hint}
                </div>
                <div className="rrow" style={{ flexWrap: 'wrap' }}>
                  <span className="rnode" style={{ fontSize: 10 }}>
                    {card.relation.source_node_id}
                  </span>
                  <span style={{ fontSize: 10, color: 'var(--t2)' }}>→ {card.relation.relation_type} →</span>
                  <span className="rnode" style={{ fontSize: 10 }}>
                    {card.relation.target_node_id}
                  </span>
                  <span className="badge b-gray" style={{ fontSize: 9 }}>
                    {card.relation.confidence}
                  </span>
                </div>
                <p className="muted" style={{ fontSize: 11, marginTop: 8 }}>
                  provenance：{card.relation.provenance} · {card.relation.provenance_detail || '—'}
                </p>
                <div className="ann-actions">
                  <button type="button" className="btn btn-ok btn-sm" disabled={loading} onClick={() => act('confirm')}>
                    ✓ 确认
                  </button>
                  <button type="button" className="btn btn-no btn-sm" disabled={loading} onClick={() => act('reject')}>
                    ✗ 否定
                  </button>
                  <button type="button" className="btn btn-sm" disabled={loading} onClick={() => act('unsure')}>
                    ? 不确定
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <div className={embedded ? 'max-w-3xl mx-auto' : 'relos-page max-w-3xl mx-auto'}>
      {!embedded && (
        <div className="flex items-center gap-3 mb-8">
          <ClipboardCheck className="w-6 h-6" style={{ color: 'var(--amber)' }} />
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--t1)', margin: 0 }}>访谈微卡片</h1>
            <p className="muted" style={{ marginTop: 4 }}>
              阶段 2 · 微任务卡片（confirm / reject / unsure）
            </p>
          </div>
        </div>
      )}

      <div className="relos-panel mb-6">
        <p className="muted" style={{ fontWeight: 500, marginBottom: 12 }}>
          会话
        </p>
        <div className="flex flex-col md:flex-row gap-3">
          <input value={engineerId} onChange={(e) => setEngineerId(e.target.value)} className="relos-field flex-1" placeholder="engineer_id" />
          <button type="button" onClick={start} disabled={loading} className="btn btn-p">
            开始访谈
          </button>
        </div>
        {sessionId ? (
          <p className="muted" style={{ fontSize: 11, marginTop: 12 }}>
            session：<span style={{ fontFamily: 'ui-monospace, monospace' }}>{sessionId}</span>
          </p>
        ) : null}
      </div>

      {error ? (
        <div className="card mb-6" style={{ borderColor: 'var(--red)', background: 'var(--red-l)' }}>
          <p style={{ color: 'var(--red)', fontWeight: 500, margin: 0 }}>操作失败</p>
          <p className="muted" style={{ margin: '6px 0 0', color: 'var(--red)' }}>
            {error}
          </p>
        </div>
      ) : null}

      {sessionId ? (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <ChevronRight className="w-4 h-4" style={{ color: 'var(--t3)' }} />
            <p className="muted" style={{ margin: 0 }}>
              当前卡片
            </p>
          </div>

          <div className="relos-panel">
            {loading ? (
              <div className="flex items-center gap-2 muted text-sm">
                <Loader2 className="w-4 h-4 animate-spin" />
                加载中...
              </div>
            ) : null}

            {!loading && card?.type === 'done' ? <p style={{ color: 'var(--t1)' }}>{card.message}</p> : null}

            {!loading && card?.type === 'relation_confirm' ? (
              <div>
                <p className="q-num">关系确认卡</p>
                <p style={{ fontWeight: 600, color: 'var(--t1)', marginTop: 8 }}>{card.hint}</p>
                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="relos-subpanel">
                    <p className="muted" style={{ fontSize: 11 }}>
                      relation_type
                    </p>
                    <p style={{ fontFamily: 'ui-monospace, monospace', fontSize: 13, color: 'var(--t1)', marginTop: 4 }}>{card.relation.relation_type}</p>
                    <p className="muted" style={{ fontSize: 11, marginTop: 12 }}>
                      source → target
                    </p>
                    <p style={{ fontSize: 13, color: 'var(--t2)', marginTop: 4 }}>
                      {card.relation.source_node_id} → {card.relation.target_node_id}
                    </p>
                    <p className="muted" style={{ fontSize: 11, marginTop: 12 }}>
                      confidence / status
                    </p>
                    <p style={{ fontSize: 13, color: 'var(--t2)', marginTop: 4 }}>
                      {card.relation.confidence} · {card.relation.status}
                    </p>
                  </div>
                  <div className="relos-subpanel">
                    <p className="muted" style={{ fontSize: 11 }}>
                      provenance
                    </p>
                    <p style={{ fontSize: 13, color: 'var(--t2)', marginTop: 4 }}>{card.relation.provenance}</p>
                    <p className="muted" style={{ fontSize: 11, marginTop: 12 }}>
                      detail
                    </p>
                    <p style={{ fontSize: 13, color: 'var(--t2)', marginTop: 4 }}>{card.relation.provenance_detail || '—'}</p>
                  </div>
                </div>

                <div className="mt-5 flex flex-col md:flex-row gap-3">
                  <button type="button" onClick={() => act('confirm')} disabled={loading} className="btn btn-ok flex-1 justify-center">
                    ✓ 确认
                  </button>
                  <button type="button" onClick={() => act('reject')} disabled={loading} className="btn btn-no flex-1 justify-center">
                    ✗ 否定
                  </button>
                  <button type="button" onClick={() => act('unsure')} disabled={loading} className="btn flex-1 justify-center">
                    ? 不确定
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}
