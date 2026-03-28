/**
 * KBStatus — 知识库状态（原型 v2 · 系统监控）
 */
import { useState } from 'react'
import Toast from '../components/Toast'

const REL_TYPE_DIST = [
  ['INDICATES', '4,231', 0.79],
  ['PRODUCES',  '3,120', 0.94],
  ['CAUSES',    '1,840', 0.72],
  ['AFFECTS',   '1,200', 0.68],
  ['BLOCKS',    '890',   0.81],
  ['DEPENDS_ON','630',   0.76],
  ['OPERATES',  '580',   0.88],
  ['DEPLETES',  '349',   0.71],
]

const SOURCE_DIST = [
  { label: 'IoT 自动抽取',         cnt: '7,892', pct: 61, cls: 'cf-high', badge: 'b-blue' },
  { label: '企业文档（LLM+审核）', cnt: '2,340', pct: 18, color: 'var(--teal)', badge: 'b-teal' },
  { label: '专家直接输入',          cnt: '1,450', pct: 11, color: 'var(--purple)', badge: 'b-purple' },
  { label: '公开知识标注',          cnt: '820',   pct: 6,  cls: 'cf-mid', badge: 'b-amber' },
  { label: '用户提示标注',          cnt: '338',   pct: 3,  cls: 'cf-low', badge: 'b-gray' },
]

const LAYERS = [
  { name: '层 1 · 公开知识', count: '820条',   cov: '18%', age: '平均 45 天', color: 'var(--blue)',   status: '健康' },
  { name: '层 2 · 专家知识', count: '1,450条', cov: '32%', age: '平均 12 天', color: 'var(--purple)', status: '需补充' },
  { name: '层 3 · 企业文档', count: '2,340条', cov: '50%', age: '平均 7 天',  color: 'var(--teal)',   status: '健康' },
]

export default function KBStatus() {
  const [toast, setToast] = useState(null)
  const msg = (m) => setToast({ m, k: Date.now() })

  return (
    <div className="relos-page">
      {toast && <Toast key={toast.k} msg={toast.m} />}

      <h2>
        知识库状态
        <span className="badge b-green">● 运行中</span>
      </h2>

      {/* 4列统计 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8, marginBottom: 12 }}>
        {[
          { v: '12,840', l: '活跃关系总数', c: 'var(--blue)'  },
          { v: '0.76',   l: '平均置信度',   c: 'var(--green)' },
          { v: '234',    l: '待审核关系',   c: 'var(--amber)' },
          { v: '89',     l: '已衰减废弃',   c: 'var(--t2)'    },
        ].map(s => (
          <div className="stat" key={s.l}>
            <div className="stat-v" style={{ color: s.c }}>{s.v}</div>
            <div className="stat-l">{s.l}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
        {/* 来源分布 */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>来源分布</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
            {SOURCE_DIST.map(s => (
              <div key={s.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
                  <span>{s.label}</span>
                  <span className={`badge ${s.badge}`}>{s.cnt} 条</span>
                </div>
                <div className="cbar">
                  <div
                    className={s.cls ? `cfill ${s.cls}` : 'cfill'}
                    style={{ width: `${s.pct}%`, background: s.color }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 关系类型分布 */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>关系类型分布（Top 8）</h3>
          <table className="tbl" style={{ marginTop: 8 }}>
            <thead>
              <tr><th>关系类型</th><th>数量</th><th>平均置信度</th></tr>
            </thead>
            <tbody>
              {REL_TYPE_DIST.map(([type, cnt, avg]) => (
                <tr key={type}>
                  <td><span className="badge b-blue">{type}</span></td>
                  <td style={{ fontWeight: 500 }}>{cnt}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                      <div className="cbar" style={{ width: 60 }}>
                        <div className="cfill cf-high" style={{ width: `${avg * 100}%` }} />
                      </div>
                      <span style={{ fontSize: 11 }}>{avg.toFixed(2)}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 三层知识结构健康度 */}
      <div className="card">
        <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>三层知识结构健康度</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8, marginTop: 8 }}>
          {LAYERS.map(l => (
            <div className="stat" key={l.name} style={{ borderLeft: `3px solid ${l.color}` }}>
              <div style={{ fontSize: 11, fontWeight: 500, color: l.color, marginBottom: 6 }}>{l.name}</div>
              <div style={{ fontSize: 19, fontWeight: 500, marginBottom: 3 }}>{l.count}</div>
              <div className="muted" style={{ fontSize: 10 }}>覆盖率：{l.cov}</div>
              <div className="muted" style={{ fontSize: 10 }}>知识新鲜度：{l.age}</div>
              <div style={{ marginTop: 6 }}>
                <span className={`badge ${l.status === '健康' ? 'b-green' : 'b-amber'}`}>{l.status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
