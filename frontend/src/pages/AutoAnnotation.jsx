/**
 * AutoAnnotation — 自动标注监控（原型 v2）
 * 展示：自动写入规则配置、最近高置信度写入日志、质量追踪
 */
import { useState } from 'react'
import Toast from '../components/Toast'

const AUTO_LOG = [
  { f: 'Machine_M1',      r: 'PRODUCES',    t: 'Alarm_Overheat',  c: 0.95, src: 'IoT',    ts: '10:23' },
  { f: 'Alarm_Overheat',  r: 'INDICATES',   t: 'BearingWear',     c: 0.87, src: 'LLM文档', ts: '10:24' },
  { f: 'Machine_M2',      r: 'PRODUCES',    t: 'Alarm_Vibration', c: 0.93, src: 'IoT',    ts: '10:31' },
  { f: 'Alarm_Vibration', r: 'INDICATES',   t: 'BearingWear',     c: 0.91, src: 'IoT',    ts: '10:31' },
  { f: 'WorkOrder_WO042', r: 'BLOCKED_BY',  t: 'Machine_M1',      c: 0.88, src: '规则',   ts: '10:35' },
]

const RULES = [
  { src: 'IoT 规则抽取',   thresh: '≥ 0.90', auto: true,  notify: false,    srcCls: 'b-blue'   },
  { src: 'LLM 文档抽取',   thresh: '≥ 0.80', auto: true,  notify: 'remind', srcCls: 'b-teal'   },
  { src: 'LLM 对话抽取',   thresh: '-',      auto: false, notify: 'approve',srcCls: 'b-purple'  },
  { src: '历史统计',        thresh: '≥ 0.75', auto: 'pending', notify: 'remind', srcCls: 'b-gray' },
]

export default function AutoAnnotation() {
  const [toast, setToast] = useState(null)
  const msg = (m) => setToast({ m, k: Date.now() })

  return (
    <div className="relos-page">
      {toast && <Toast key={toast.k} msg={toast.m} />}

      <h2>
        自动标注监控
        <span className="badge b-green">置信度 ≥ 0.80 自动写入</span>
      </h2>
      <p className="muted" style={{ marginBottom: 12 }}>
        以下关系由系统从 IoT 事件 / LLM 抽取自动写入图谱，无需人工干预。实时更新，可追溯。
      </p>

      {/* 规则配置表 */}
      <div className="card" style={{ marginBottom: 10 }}>
        <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>自动标注规则配置</h3>
        <table className="tbl" style={{ marginTop: 8 }}>
          <thead>
            <tr>
              <th>来源类型</th>
              <th>置信度阈值</th>
              <th>自动写入</th>
              <th>通知用户</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {RULES.map((r, i) => (
              <tr key={i}>
                <td><span className={`badge ${r.srcCls}`}>{r.src}</span></td>
                <td>{r.thresh}</td>
                <td>
                  {r.auto === true   && <span className="badge b-green">是</span>}
                  {r.auto === false  && <span className="badge b-red">否</span>}
                  {r.auto === 'pending' && <span className="badge b-amber">待确认</span>}
                </td>
                <td>
                  {r.notify === false   && <span style={{ color: 'var(--t3)' }}>否</span>}
                  {r.notify === 'remind'  && <span className="badge b-amber">提醒</span>}
                  {r.notify === 'approve' && <span className="badge b-amber">待审批</span>}
                </td>
                <td><button className="btn btn-sm" onClick={() => msg(`配置「${r.src}」规则`)}>配置</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {/* 最近自动写入日志 */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>最近自动写入（高置信度）</h3>
          {AUTO_LOG.map((r, i) => (
            <div className="rrow" key={i}>
              <span className="rnode" style={{ fontSize: 10 }}>{r.f}</span>
              <span style={{ fontSize: 10, color: 'var(--t2)' }}>→{r.r}→</span>
              <span className="rnode" style={{ fontSize: 10 }}>{r.t}</span>
              <div className="cbar" style={{ flex: 1 }}>
                <div className="cfill cf-high" style={{ width: `${r.c * 100}%` }} />
              </div>
              <span style={{ fontSize: 10, color: 'var(--green)', minWidth: 28 }}>{r.c}</span>
              <span className="badge b-gray" style={{ fontSize: 9 }}>{r.src}</span>
              <span style={{ fontSize: 10, color: 'var(--t3)' }}>{r.ts}</span>
            </div>
          ))}
        </div>

        {/* 质量追踪 */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>自动标注质量追踪</h3>
          <p className="muted" style={{ marginBottom: 8 }}>基于用户后续反馈计算</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
            <div className="stat">
              <div className="stat-v" style={{ color: 'var(--green)' }}>94.2%</div>
              <div className="stat-l">IoT规则准确率</div>
            </div>
            <div className="stat">
              <div className="stat-v" style={{ color: 'var(--blue)' }}>81.7%</div>
              <div className="stat-l">LLM文档准确率</div>
            </div>
          </div>
          <div className="hdiv" />
          <div style={{ fontSize: 11, color: 'var(--t2)', lineHeight: 1.7 }}>
            过去 7 天：用户否定了 23 条自动写入关系（占总量 1.8%）<br />
            否定最多的关系类型：<span className="badge b-amber">INDICATES</span> 共 14 次<br />
            建议降低 INDICATES 类型的自动写入阈值至 0.85
          </div>
        </div>
      </div>
    </div>
  )
}
