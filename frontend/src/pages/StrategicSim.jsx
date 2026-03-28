/**
 * 战略扩产模拟 + 资源配置（S-12 / S-11）— 严格对齐 relos_workbench v2：card / stat / rrow / cbar / btn / ann-src / upz
 */
import { useState, useCallback } from 'react'
import { TrendingUp, Zap, CheckCircle } from 'lucide-react'
import { runStrategicSimulation, getResourceOptimization } from '../api/client'
import ConfidenceBar from '../components/ConfidenceBar'

const RISK_LABEL = { high: '高风险', medium: '中等风险', low: '可接受' }

function RiskChangeRow({ label, change, last }) {
  const isRise = change > 0
  const color = isRise ? 'var(--red)' : 'var(--green)'
  return (
    <div
      className="rrow"
      style={{
        justifyContent: 'space-between',
        borderBottom: last ? 'none' : undefined,
        marginBottom: last ? 0 : undefined,
      }}
    >
      <span className="muted">{label}</span>
      <span className="tabular-nums" style={{ fontWeight: 600, fontSize: 13, color }}>
        {isRise ? '+' : ''}
        {change.toFixed(1)}% {isRise ? '↑' : '↓'}
      </span>
    </div>
  )
}

export default function StrategicSim() {
  const [expansion, setExpansion] = useState(30)
  const [simResult, setSimResult] = useState(null)
  const [resources, setResources] = useState(null)
  const [loading, setLoading] = useState(false)
  const [resLoading, setResLoading] = useState(false)
  const [simError, setSimError] = useState(null)
  const [resError, setResError] = useState(null)

  const runSim = useCallback(async () => {
    setLoading(true)
    setSimError(null)
    try {
      const data = await runStrategicSimulation(expansion)
      setSimResult(data)
    } catch (e) {
      setSimResult(null)
      setSimError(e.message || '战略模拟请求失败，请检查后端与 Neo4j。')
    } finally {
      setLoading(false)
    }
  }, [expansion])

  const loadResources = async () => {
    setResLoading(true)
    setResError(null)
    try {
      const data = await getResourceOptimization()
      setResources(data)
    } catch (e) {
      setResources(null)
      setResError(e.message || '加载资源配置失败。')
    } finally {
      setResLoading(false)
    }
  }

  const riskLevel = simResult?.risk_level || 'low'
  const riskBadge = riskLevel === 'high' ? 'b-red' : riskLevel === 'medium' ? 'b-amber' : 'b-green'
  const riskColor = riskLevel === 'high' ? 'var(--red)' : riskLevel === 'medium' ? 'var(--amber)' : 'var(--green)'
  const riskBg = riskLevel === 'high' ? 'var(--red-l)' : riskLevel === 'medium' ? 'var(--amber-l)' : 'var(--green-l)'

  return (
    <div className="relos-page">
      <h2>
        战略模拟与资源配置 <span className="badge b-teal">S-11 / S-12</span>
      </h2>
      <div className="muted mb12">资源配置优化 · 战略扩产影响推演（布局与知识库状态页 stat / rrow 一致）</div>

      <div className="g2">
        <div>
          <h3>扩产影响模拟（S-12）</h3>

          <div className="card mb12">
            <div className="rrow" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
              <span className="muted" style={{ fontSize: 12 }}>
                扩产比例
              </span>
              <span className="tabular-nums stat-v" style={{ marginBottom: 0, fontSize: 22, color: 'var(--blue)' }}>
                +{expansion}%
              </span>
            </div>
            <input
              type="range"
              min={5}
              max={60}
              step={5}
              value={expansion}
              onChange={(e) => setExpansion(Number(e.target.value))}
              style={{ width: '100%' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--t3)', marginTop: 4 }}>
              <span>保守 +5%</span>
              <span>激进 +60%</span>
            </div>

            <div style={{ display: 'flex', gap: 2, marginTop: 12 }}>
              {[5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60].map((v) => (
                <div
                  key={v}
                  style={{
                    flex: 1,
                    height: 5,
                    borderRadius: 3,
                    background:
                      v <= expansion
                        ? v <= 15
                          ? 'var(--green)'
                          : v <= 25
                            ? 'var(--amber)'
                            : 'var(--red)'
                        : 'var(--b1)',
                  }}
                />
              ))}
            </div>

            <button
              type="button"
              className="btn btn-p mt-3 w-full justify-center disabled:cursor-not-allowed disabled:opacity-40"
              onClick={runSim}
              disabled={loading}
            >
              {loading ? (
                <>模拟中…</>
              ) : (
                <>
                  <Zap style={{ width: 16, height: 16 }} />
                  运行模拟
                </>
              )}
            </button>
            {simError ? (
              <p className="muted mt8" style={{ color: 'var(--red)', fontSize: 12 }}>
                {simError}
              </p>
            ) : null}
          </div>

          {simResult && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="g2 mb10">
                <div className="stat" style={{ borderLeft: '3px solid var(--red)' }}>
                  <div className="stat-v" style={{ color: 'var(--red)', fontSize: 18 }}>
                    +{simResult.delivery_risk_change_pct?.toFixed(1)}%
                  </div>
                  <div className="stat-l">交付风险</div>
                </div>
                <div className="stat" style={{ borderLeft: '3px solid var(--amber)' }}>
                  <div className="stat-v" style={{ color: 'var(--amber)', fontSize: 18 }}>
                    +{simResult.failure_rate_change_pct?.toFixed(1)}%
                  </div>
                  <div className="stat-l">设备故障率</div>
                </div>
                <div className="stat" style={{ borderLeft: '3px solid var(--amber)' }}>
                  <div className="stat-v" style={{ color: 'var(--amber)', fontSize: 18 }}>
                    +{simResult.quality_risk_change_pct?.toFixed(1)}%
                  </div>
                  <div className="stat-l">质量缺陷率</div>
                </div>
                <div className="stat" style={{ borderLeft: `3px solid ${riskColor}`, background: riskBg }}>
                  <div className="stat-v" style={{ color: riskColor, fontSize: 15 }}>
                    <span className={`badge ${riskBadge}`} style={{ verticalAlign: 'middle' }}>
                      {RISK_LABEL[riskLevel]}
                    </span>
                  </div>
                  <div className="stat-l">综合评级 · +{simResult.expansion_pct}%</div>
                </div>
              </div>

              <div className="card">
                <h3 style={{ marginBottom: 8 }}>关键风险指标变化</h3>
                <RiskChangeRow label="交付风险" change={simResult.delivery_risk_change_pct} />
                <RiskChangeRow label="设备故障率" change={simResult.failure_rate_change_pct} />
                <RiskChangeRow label="质量缺陷率" change={simResult.quality_risk_change_pct} last />
              </div>

              <div className="card">
                <h3 style={{ marginBottom: 8 }}>影响路径</h3>
                <div>
                  {simResult.causal_chain?.map((step, i) => (
                    <div key={i} className="tl-item">
                      <span className="tl-dot" />
                      <span style={{ fontSize: 12, color: 'var(--t1)', lineHeight: 1.5 }}>{step}</span>
                    </div>
                  ))}
                </div>
              </div>

              {simResult.recommendations?.length > 0 && (
                <div className="card">
                  <h3 style={{ marginBottom: 8 }}>扩产前建议</h3>
                  <div className="ann-src" style={{ marginBottom: 0 }}>
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: 'var(--t1)' }}>
                      {simResult.recommendations.map((rec, i) => (
                        <li key={i} style={{ marginBottom: 6 }}>
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div>
          <div className="rrow" style={{ justifyContent: 'space-between', marginBottom: 8, flexWrap: 'wrap' }}>
            <h3 style={{ marginBottom: 0 }}>资源配置优化（S-11）</h3>
            {!resources && (
              <button
                type="button"
                className="btn btn-p btn-sm disabled:cursor-not-allowed disabled:opacity-40"
                onClick={loadResources}
                disabled={resLoading}
              >
                {resLoading ? '加载中…' : '加载建议'}
              </button>
            )}
          </div>

          {!resources && !resLoading && (
            <div className="upz mb12">
              <TrendingUp style={{ width: 28, height: 28, margin: '0 auto 8px', color: 'var(--t3)' }} />
              <p className="muted" style={{ marginBottom: 8 }}>
                点击下方按钮加载资源配置优化方案
              </p>
              <button type="button" className="btn btn-p btn-sm justify-center" onClick={loadResources}>
                加载建议
              </button>
            </div>
          )}

          {resLoading && <p className="muted">加载中…</p>}

          {resError ? (
            <div className="card mb12" style={{ borderColor: 'var(--red)', background: 'var(--red-l)' }}>
              <p style={{ fontSize: 12, color: 'var(--red)', margin: 0 }}>{resError}</p>
            </div>
          ) : null}

          {resources && (!resources.recommendations || resources.recommendations.length === 0) ? (
            <div className="card mb12">
              <p className="muted" style={{ fontSize: 12, margin: 0 }}>
                当前图谱中无 ISSUE__REQUIRES__RESOURCE 等资源优化关系。开发环境可运行{' '}
                <code style={{ fontSize: 11 }}>python scripts/seed_demo_scenarios.py</code> 注入演示数据。
              </p>
            </div>
          ) : null}

          {resources && resources.recommendations?.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {resources.recommendations.map((rec) => (
                <div key={rec.rank} className="card">
                  <div className="rrow" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 10, marginBottom: 8 }}>
                    <div style={{ flex: 1, minWidth: 160 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                        <span className="badge b-purple">{rec.rank}</span>
                        <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--t1)' }}>{rec.resource_name}</span>
                      </div>
                      <p className="muted" style={{ fontSize: 12, margin: 0 }}>
                        {rec.impact_description}
                      </p>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <p className="tabular-nums stat-v" style={{ marginBottom: 0, fontSize: 20, color: 'var(--green)' }}>
                        {rec.roi_pct}%
                      </p>
                      <p className="muted stat-l" style={{ margin: 0 }}>
                        ROI
                      </p>
                    </div>
                  </div>
                  <div className="rrow" style={{ justifyContent: 'space-between', marginBottom: 0 }}>
                    <span className="muted" style={{ fontSize: 11 }}>
                      投入：¥{(rec.investment_rmb / 10000).toFixed(0)} 万
                    </span>
                    <div style={{ width: 'min(200px, 55%)' }}>
                      <ConfidenceBar value={rec.roi_pct / 100} size="sm" showLabel={false} />
                    </div>
                  </div>
                </div>
              ))}

              {resources.priority_action && (
                <div className="card" style={{ background: 'var(--blue-l)', borderColor: 'var(--blue)' }}>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                    <CheckCircle style={{ width: 18, height: 18, flexShrink: 0, color: 'var(--blue)' }} />
                    <p style={{ fontSize: 12, color: 'var(--blue-ink)', margin: 0 }}>{resources.priority_action}</p>
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
