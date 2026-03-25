/**
 * RelOS API Client
 * 连接后端 FastAPI (localhost:8000)，通过 Vite dev proxy 转发
 */

const BASE_URL = '/v1'

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
    throw new Error(err.detail || `HTTP ${res.status}`)
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
    throw new Error(err.detail || `HTTP ${res.status}`)
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

export const createRelation = (payload) =>
  request('POST', '/relations/', payload)

export const approveRelation = (relationId) =>
  request('POST', `/relations/${relationId}/approve`)

export const rejectRelation = (relationId) =>
  request('POST', `/relations/${relationId}/reject`)

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
