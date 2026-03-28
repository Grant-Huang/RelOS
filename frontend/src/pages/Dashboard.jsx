/**
 * Dashboard — 运行时仪表盘（原型 v2 · 用户前端）
 */
import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import Toast from '../components/Toast'

const EV_TYPES = [
  { type: 'auto',   label: '过热报警 M1',     rel: { f: 'Machine_M1',    r: 'PRODUCES',  t: 'Alarm_Overheat'  }, c: 0.95 },
  { type: 'prompt', label: '振动异常 M3',      rel: { f: 'Machine_M3',    r: 'INDICATES', t: 'BearingWear'     }, c: 0.62 },
  { type: 'auto',   label: '工单 WO-043 延误', rel: { f: 'Alarm_Overheat',r: 'AFFECTS',   t: 'WorkOrder_WO043' }, c: 0.83 },
  { type: 'new',    label: '库存低位预警',     rel: { f: 'Material_BRG',  r: 'DEPLETES',  t: 'Inventory_BRG'   }, c: 0.77 },
]

const INIT_EVENTS = [
  { ...EV_TYPES[0], ts: '10:23' },
  { ...EV_TYPES[1], ts: '10:24' },
  { ...EV_TYPES[2], ts: '10:31' },
]

function EventItem({ ev }) {
  const label = ev.type === 'auto' ? '自动标注' : ev.type === 'prompt' ? '待确认' : '新事件'
  const cls = ev.c >= 0.8 ? 'cf-high' : ev.c >= 0.65 ? 'cf-mid' : 'cf-low'
  return (
    <div className={`ev-item ev-${ev.type}`}>
      <div className="ev-time">{ev.ts} · {label}</div>
      <div style={{ fontWeight: 500, color: 'var(--t1)' }}>{ev.label}</div>
      <div className="ev-rel">
        <span className="rnode">{ev.rel.f}</span>
        <span style={{ fontSize: 10, color: 'var(--t2)' }}>→ {ev.rel.r} →</span>
        <span className="rnode">{ev.rel.t}</span>
        <div className="cbar" style={{ maxWidth: 50 }}><div className={`cfill ${cls}`} style={{ width: `${ev.c * 100}%` }} /></div>
        <span style={{ fontSize: 10, fontWeight: 500 }}>{ev.c.toFixed(2)}</span>
        {ev.type === 'auto'
          ? <span className="badge b-green" style={{ fontSize: 9 }}>自动写入</span>
          : <span className="badge b-amber" style={{ fontSize: 9 }}>待确认</span>
        }
      </div>
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [events, setEvents] = useState(INIT_EVENTS)
  const [evIdx, setEvIdx] = useState(0)
  const [toast, setToast] = useState(null)
  const msg = useCallback((m, c = 'var(--blue)') => setToast({ m, c, k: Date.now() }), [])

  const addEvent = () => {
    const ev = EV_TYPES[evIdx % EV_TYPES.length]
    setEvents(prev => [{ ...ev, ts: new Date().toTimeString().slice(0, 5) }, ...prev.slice(0, 5)])
    setEvIdx(i => i + 1)
    msg('新事件：' + ev.label)
  }

  return (
    <div style={{ padding: '16px 20px' }}>
      {toast && <Toast key={toast.k} msg={toast.m} color={toast.c} />}

      <h2 className="page-h2">
        运行时仪表盘
        <span className="badge b-blue">用户前端 · 操作员视角</span>
      </h2>

      {/* 4列统计 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8, marginBottom: 12 }}>
        {[
          { v: '47',     l: '今日已处理报警',  c: 'var(--green)' },
          { v: '89%',    l: '自动标注命中率',  c: 'var(--blue)'  },
          { v: '3',      l: '待人工确认',      c: 'var(--amber)' },
          { v: '12,840', l: '图谱关系总数',    c: 'var(--t1)'    },
        ].map(s => (
          <div className="stat-card" key={s.l}>
            <div className="stat-value" style={{ color: s.c }}>{s.v}</div>
            <div className="stat-label">{s.l}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {/* 实时事件流 */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>
            实时事件流 <span className="badge b-gray" style={{ fontSize: 10 }}>● 实时</span>
          </h3>
          {events.map((ev, i) => <EventItem key={i} ev={ev} />)}
          <div style={{ textAlign: 'center', marginTop: 8 }}>
            <button className="btn btn-sm" onClick={addEvent}>+ 模拟新事件</button>
          </div>
        </div>

        {/* 决策建议 */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>当前活跃决策建议</h3>

          <div className="ann-card" style={{ borderLeft: '3px solid var(--amber)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span className="badge b-amber">待确认</span>
              <span style={{ fontSize: 10, color: 'var(--t3)' }}>优先级：高</span>
            </div>
            <div style={{ fontWeight: 500, fontSize: 13, marginBottom: 6 }}>1号机过热 → 建议暂停设备</div>
            <div className="ann-src">
              触发：<span className="ent-alarm">过热报警</span> 已持续 12 分钟<br />
              图谱推断：<span className="ent-issue">轴承磨损</span> 可能性 87%<br />
              影响：<span className="ent-wo">工单WO-043</span> 延误风险 74%
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
              <button className="btn btn-ok btn-sm" onClick={() => msg('已确认：暂停1号机', 'var(--green)')}>✓ 确认执行</button>
              <button className="btn btn-no btn-sm" onClick={() => msg('已拒绝，请手动处理', 'var(--red)')}>✗ 拒绝</button>
              <button className="btn btn-sm" onClick={() => msg('已转交给班组长')}>转交</button>
            </div>
          </div>

          <div className="ann-card" style={{ borderLeft: '3px solid var(--blue)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span className="badge b-blue">低置信度·待审</span>
              <span style={{ fontSize: 10, color: 'var(--t3)' }}>置信度：0.61</span>
            </div>
            <div style={{ fontWeight: 500, fontSize: 13, marginBottom: 6 }}>振动报警 M3 → 根因？</div>
            <div className="ann-src">
              系统不确定：<span className="ent-issue">轴承磨损</span>(0.61) vs <span className="ent-issue">安装偏差</span>(0.39)<br />
              历史仅 3 次相似案例
            </div>
            <div style={{ marginTop: 8 }}>
              <button className="btn btn-sm" onClick={() => navigate('/hitl')}>去标注 →</button>
            </div>
          </div>
        </div>
      </div>

      {/* 标注来源分布 */}
      <div className="card" style={{ marginTop: 10 }}>
        <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>标注来源分布（今日）</h3>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {[
            { label: 'IoT 自动抽取', pct: 78, cls: 'cf-high', c: 'var(--green)' },
            { label: '用户提示确认', pct: 14, cls: 'cf-mid',  c: 'var(--amber)' },
            { label: '专家手动输入', pct: 8,  cls: 'cf-low',  c: 'var(--red)'   },
          ].map(s => (
            <div key={s.label} style={{ flex: 1, minWidth: 120 }}>
              <div style={{ fontSize: 11, color: 'var(--t2)', marginBottom: 4 }}>{s.label}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div className="cbar"><div className={`cfill ${s.cls}`} style={{ width: `${s.pct}%` }} /></div>
                <span style={{ fontSize: 11, fontWeight: 500, color: s.c }}>{s.pct}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
