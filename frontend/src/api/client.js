/**
 * RelOS API Client
 * 连接后端 FastAPI (localhost:8000)，通过 Vite dev proxy 转发
 */

const BASE_URL = '/v1'

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

// ── 健康检查 ──────────────────────────────────────────
export const healthCheck = () => request('GET', '/health')

// ── 决策分析 ──────────────────────────────────────────
export const analyzeAlarm = (payload) =>
  request('POST', '/decisions/analyze-alarm', payload)

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
