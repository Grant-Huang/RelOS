/**
 * HITLQueue — 提示标注工作区（Human-in-the-Loop，原型 v2）
 * 置信度 0.50–0.79，需人工确认
 */
import { useState } from 'react'
import Toast from '../components/Toast'

const INIT_QUEUE = [
  { id: 0, cat: 'alarm',   src: '振动异常 M3 (10:31) — SCADA 事件日志',  f: 'Alarm_Vibration',    r: 'INDICATES', t: 'BearingWear',     c: 0.62, why: '仅观测3次，证据不足' },
  { id: 1, cat: 'alarm',   src: '高电流 M2 (09:45) — 控制系统日志',      f: 'Alarm_HighCurrent',  r: 'INDICATES', t: 'MotorOverload',    c: 0.68, why: '与历史案例部分匹配' },
  { id: 2, cat: 'quality', src: '质检结果 BATCH-221 — QMS 导出',        f: 'Process_P3',         r: 'CAUSES',    t: 'Defect_DimError',  c: 0.57, why: '工艺参数偏离，根因不确定' },
  { id: 3, cat: 'quality', src: '维修记录 2026-01-15 — CMMS',          f: 'Machine_M4',         r: 'AFFECTS',   t: 'Quality_Batch',   c: 0.71, why: '关联度偏低，需专家确认' },
  { id: 4, cat: 'alarm',   src: '压力下降 M5 (11:02) — SCADA',         f: 'Alarm_PressureDrop', r: 'INDICATES', t: 'SealFailure',      c: 0.59, why: '首次出现此类报警' },
  { id: 5, cat: 'wo',      src: '工单 WO-041 延误 — MES',             f: 'Alarm_Overheat',     r: 'AFFECTS',   t: 'WorkOrder_WO041', c: 0.73, why: '间接影响，置信度中等' },
]

const FILTERS = [
  { key: 'all',     label: '全部' },
  { key: 'alarm',   label: '报警类' },
  { key: 'quality', label: '质量类' },
  { key: 'wo',      label: '工单类' },
]

const CAT_LABEL = { alarm: '报警类', quality: '质量类', wo: '工单类' }

export default function HITLQueue() {
  const [queue, setQueue] = useState(INIT_QUEUE.map(a => ({ ...a, st: 'pending' })))
  const [filter, setFilter] = useState('all')
  const [toast, setToast] = useState(null)
  const msg = (m, c = 'var(--blue)') => setToast({ m, c, k: Date.now() })

  const act = (id, st) => {
    setQueue(prev => prev.map(a => a.id === id ? { ...a, st } : a))
    const msgs = { approve: '已确认并写入图谱 ✓', reject: '已拒绝，置信度下调', modify: '请选择正确关系类型', skip: '已跳过' }
    const colors = { approve: 'var(--green)', reject: 'var(--red)', modify: 'var(--blue)', skip: 'var(--t2)' }
    msg(msgs[st] || '已跳过', colors[st] || 'var(--blue)')
  }

  const approveAll = () => {
    setQueue(prev => prev.map(a =>
      (filter === 'all' || a.cat === filter) ? { ...a, st: 'approve' } : a
    ))
    msg('已全部确认写入', 'var(--green)')
  }

  const counts = {
    all:     queue.filter(a => a.st === 'pending').length,
    alarm:   queue.filter(a => a.st === 'pending' && a.cat === 'alarm').length,
    quality: queue.filter(a => a.st === 'pending' && a.cat === 'quality').length,
    wo:      queue.filter(a => a.st === 'pending' && a.cat === 'wo').length,
  }

  const visible = queue.filter(a =>
    a.st === 'pending' && (filter === 'all' || a.cat === filter)
  )

  return (
    <div className="relos-page">
      {toast && <Toast key={toast.k} msg={toast.m} color={toast.c} />}

      <h2>
        提示标注工作区
        <span className="badge b-amber">置信度 0.50–0.79 · 需人工确认</span>
      </h2>
      <p className="muted" style={{ marginBottom: 12 }}>
        以下关系系统无法自信地判断，请您结合现场经验确认。每次确认都会强化系统的学习。
      </p>

      {/* 筛选栏 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <span className="muted">筛选：</span>
        <div>
          {FILTERS.map(f => (
            <span
              key={f.key}
              className={`chip ${filter === f.key ? 'on' : ''}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label} ({counts[f.key] ?? 0})
            </span>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        <button className="btn btn-ok btn-sm" onClick={approveAll}>全部确认</button>
        <button className="btn btn-sm" onClick={() => msg('已跳过全部')}>跳过全部</button>
      </div>

      {visible.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 32, color: 'var(--t2)' }}>
          ✓ 所有待标注项已处理
        </div>
      ) : (
        visible.map(a => (
          <div className="ann-card" key={a.id}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className={`badge ${a.c < 0.65 ? 'b-red' : a.c < 0.75 ? 'b-amber' : 'b-blue'}`}>
                  {a.c.toFixed(2)} 置信度
                </span>
                <span className="badge b-gray">{CAT_LABEL[a.cat]}</span>
              </div>
              <span style={{ fontSize: 10, color: 'var(--t3)' }}>不确定原因：{a.why}</span>
            </div>
            <div className="ann-src" style={{ marginBottom: 8 }}>来源：{a.src}</div>
            <div className="rrow" style={{ marginBottom: 8 }}>
              <span className="rnode">{a.f}</span>
              <span style={{ fontSize: 11, color: 'var(--t2)' }}>→ {a.r} →</span>
              <span className="rnode">{a.t}</span>
              <div className="cbar" style={{ flex: 1 }}>
                <div
                  className={`cfill ${a.c < 0.65 ? 'cf-low' : a.c < 0.75 ? 'cf-mid' : 'cf-high'}`}
                  style={{ width: `${a.c * 100}%` }}
                />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <button className="btn btn-ok btn-sm" onClick={() => act(a.id, 'approve')}>✓ 正确，写入</button>
              <button className="btn btn-no btn-sm" onClick={() => act(a.id, 'reject')}>✗ 错误</button>
              <button className="btn btn-sm" onClick={() => act(a.id, 'modify')}>✎ 修改关系类型</button>
              <button className="btn btn-sm" onClick={() => act(a.id, 'skip')}>跳过</button>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
