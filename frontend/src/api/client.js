/**
 * RelOS API Client
 * 连接后端 FastAPI (localhost:8000)，通过 Vite dev proxy 转发
 */

const BASE_URL = '/v1'

/** FastAPI 错误体：detail 可能为 string 或校验错误数组 */
function formatFetchDetail(payload) {
  if (!payload || typeof payload !== 'object') return null
  const d = payload.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) {
    return d
      .map((x) => (x && typeof x === 'object' && x.msg ? x.msg : JSON.stringify(x)))
      .join('; ')
  }
  if (d && typeof d === 'object') return JSON.stringify(d)
  return null
}

function getSessionId() {
  const key = 'relos_session_id'
  let sid = localStorage.getItem(key)
  if (!sid) {
    sid = `sess-${Math.random().toString(16).slice(2)}`
    localStorage.setItem(key, sid)
  }
  return sid
}

async function request(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body) opts.body = JSON.stringify(body)

  const res = await fetch(`${BASE_URL}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = formatFetchDetail(err) || err.detail || `HTTP ${res.status}`
    throw new Error(msg)
  }
  return res.json()
}

export const postTelemetryEvent = (payload) =>
  request('POST', '/telemetry/events', {
    session_id: getSessionId(),
    actor_role: 'frontline_engineer',
    actor_id: 'anonymous',
    ...payload,
  })

// ── 健康检查 ──────────────────────────────────────────
export const healthCheck = () => request('GET', '/health')

// ── 决策分析 ──────────────────────────────────────────
export const analyzeAlarm = (payload) =>
  request('POST', '/decisions/analyze-alarm', payload)

export async function analyzeAlarmStream(payload, onEvent) {
  const res = await fetch(`${BASE_URL}/decisions/analyze-alarm/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = formatFetchDetail(err) || err.detail || `HTTP ${res.status}`
    throw new Error(msg)
  }

  const reader = res.body?.getReader()
  if (!reader) throw new Error('浏览器不支持流式读取')

  const decoder = new TextDecoder('utf-8')
  let buf = ''

  const parseChunk = (raw) => {
    // 每个 SSE 事件以空行分隔
    buf += raw
    const parts = buf.split('\n\n')
    buf = parts.pop() || ''
    for (const part of parts) {
      const lines = part.split('\n').filter(Boolean)
      let event = 'message'
      let dataStr = ''
      for (const line of lines) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        if (line.startsWith('data:')) dataStr += line.slice(5).trim()
      }
      if (!dataStr) continue
      let data = null
      try {
        data = JSON.parse(dataStr)
      } catch {
        data = { raw: dataStr }
      }
      onEvent?.(event, data)
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    parseChunk(decoder.decode(value, { stream: true }))
  }
}

export const streamAnswer = (payload) =>
  request('POST', '/decisions/stream-answer', payload)

// ── 关系管理 ──────────────────────────────────────────
export const listRelations = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return request('GET', `/relations/${qs ? '?' + qs : ''}`)
}

/** 待审核队列（后端路径：GET /relations/pending-review） */
export const listPendingRelations = (limit = 50) =>
  request('GET', `/relations/pending-review?limit=${limit}`)

export const createRelation = (payload) =>
  request('POST', '/relations/', payload)

/** 人工反馈：确认/否定关系（触发 Relation Core 更新） */
export const submitRelationFeedback = (relationId, body) =>
  request('POST', `/relations/${relationId}/feedback`, body)

export const approveRelation = (relationId) =>
  request('POST', `/relations/${relationId}/approve`)

export const rejectRelation = (relationId) =>
  request('POST', `/relations/${relationId}/reject`)

export const listTelemetryEvents = (limit = 50) =>
  request('GET', `/telemetry/events?limit=${limit}`)

export const listDocuments = () => request('GET', '/documents/')

export const annotateDocumentRelation = (docId, relId, body) =>
  request('POST', `/documents/${docId}/annotate/${relId}`, body)

export const commitDocument = (docId) => request('POST', `/documents/${docId}/commit`, {})

// ── 场景接口 ──────────────────────────────────────────
export const getRiskRadar = () => request('GET', '/scenarios/risk-radar')
export const getLineEfficiency = () => request('GET', '/scenarios/line-efficiency')
export const getCrossDeptAnalysis = () => request('GET', '/scenarios/cross-dept-analysis')
export const getIssueResolution = () => request('GET', '/scenarios/issue-resolution')
export const getResourceOptimization = () => request('GET', '/scenarios/resource-optimization')
export const runStrategicSimulation = (expansionPct) =>
  request('POST', '/scenarios/strategic-simulation', { expansion_pct: expansionPct })

// ── 图谱统计 ──────────────────────────────────────────
export const getMetrics = () => request('GET', '/metrics')

// ── 配置与演示数据（data/demo/*.json，由后端读取）──────────
export const getQuickAlarmsConfig = async () => {
  const res = await request('GET', '/config/quick-alarms')
  return res?.data?.items ?? []
}

export const getTextSamplesConfig = async () => {
  const res = await request('GET', '/config/text-samples')
  return res?.data?.samples ?? {}
}

// ── 公开知识：纯文本抽取（不入库）────────────────────────
export const extractPublicKnowledge = (payload) =>
  request('POST', '/knowledge/public/extract', payload)

// ── 运行时仪表盘事件流（来自埋点）────────────────────────
export const getRuntimeFeed = (limit = 12) =>
  request('GET', `/telemetry/runtime-feed?limit=${limit}`)

// ── 专家初始化 ────────────────────────────────────────
export const expertInitRelation = (payload) =>
  request('POST', '/expert-init', payload)

// ── 文档上传 ──────────────────────────────────────────
export const uploadDocument = async (file) => {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE_URL}/documents/upload`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) throw new Error(`上传失败: HTTP ${res.status}`)
  return res.json()
}

export const getDocument = (docId) => request('GET', `/documents/${docId}`)

export const clarifyDocument = (docId, payload) =>
  request('POST', `/documents/${docId}/clarify`, payload)

// ── 访谈微卡片（阶段2）────────────────────────────────
export const createInterviewSession = (payload) =>
  request('POST', '/interview/sessions', payload)

export const getInterviewNextCard = (sessionId) =>
  request('GET', `/interview/sessions/${sessionId}/next-card`)

export const submitInterviewCard = (sessionId, payload) =>
  request('POST', `/interview/sessions/${sessionId}/submit-card`, payload)
