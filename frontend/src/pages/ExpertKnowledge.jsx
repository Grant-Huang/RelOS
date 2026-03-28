/**
 * ExpertKnowledge — 专家知识采集（原型 v2 · 知识层 2）
 * 结构化访谈，将专家隐性经验转化为可计算的关系知识
 */
import { useState } from 'react'
import Toast from '../components/Toast'

const SCENARIOS = [
  {
    id: 0, name: '设备故障分析',
    qs: [
      { q: '在您的经验中，过热报警最常见的根本原因是什么？请列举前3位。', ph: '例如：轴承磨损、冷却液不足、转速过高...' },
      { q: '哪些设备特征（型号、使用年限、工况）会影响故障发生概率？', ph: '例如：老设备轴承故障率更高，高负载工况下冷却问题更常见...' },
      { q: '遇到过热报警后，您的标准处置步骤是什么？有哪些关键判断节点？', ph: '例如：先确认温度数值，超过85°C立即停机...' },
    ],
  },
  {
    id: 1, name: '工单延误分析',
    qs: [
      { q: '工单延误最常见的直接原因有哪些？设备问题、物料短缺还是人员问题？', ph: '' },
      { q: '哪类设备停机对工单影响最大？', ph: '' },
      { q: '您如何在工单开始前预判延误风险？', ph: '' },
    ],
  },
  {
    id: 2, name: '质量异常分析',
    qs: [
      { q: '这类缺陷最可能出现在哪个工序？有无规律性？', ph: '' },
      { q: '物料批次与质量异常有关联吗？如何判断？', ph: '' },
      { q: '操作员技能水平对质量有多大影响？哪些操作最容易出错？', ph: '' },
    ],
  },
]

const SAMPLE_RELS = [
  [
    { f: '过热报警', r: 'INDICATES', t: '轴承磨损',  c: 0.82 },
    { f: '轴承磨损', r: 'CAUSES',    t: '设备停机',  c: 0.75 },
  ],
  [
    { f: '设备停机', r: 'AFFECTS',   t: '生产工单',  c: 0.88 },
    { f: '过热报警', r: 'INDICATES', t: '冷却液不足', c: 0.63 },
  ],
  [
    { f: '轴承磨损', r: 'INDICATES', t: '过热报警',  c: 0.79 },
    { f: '过热报警', r: 'BLOCKS',    t: 'Production', c: 0.84 },
  ],
]

export default function ExpertKnowledge() {
  const [scenario, setScenario] = useState(null)
  const [qIdx, setQIdx] = useState(0)
  const [ans, setAns] = useState('')
  const [rels, setRels] = useState([])
  const [confirmed, setConfirmed] = useState(new Set())
  const [rejected, setRejected] = useState(new Set())
  const [expert, setExpert] = useState({ name: '', years: 10, domain: '机械维修' })
  const [toast, setToast] = useState(null)
  const msg = (m, c = 'var(--blue)') => setToast({ m, c, k: Date.now() })

  const selectScenario = (sc) => {
    setScenario(sc)
    setQIdx(0)
    setAns('')
    setRels([])
    setConfirmed(new Set())
    setRejected(new Set())
  }

  const submitAns = () => {
    if (!ans.trim() || ans.trim().length < 5) { msg('请填写回答后再提取', 'var(--red)'); return }
    const newRels = SAMPLE_RELS[qIdx % SAMPLE_RELS.length]
    setRels(prev => [...prev, ...newRels])
    msg(`已从回答中提取 ${newRels.length} 条候选关系`)
    if (qIdx < scenario.qs.length - 1) { setQIdx(i => i + 1); setAns('') }
    else msg('所有问题已完成！请审核候选关系', 'var(--green)')
  }

  const nextQ = () => {
    if (!scenario) { msg('请先选择场景', 'var(--red)'); return }
    if (qIdx < scenario.qs.length - 1) { setQIdx(i => i + 1); setAns('') }
    else msg('所有问题已完成！', 'var(--green)')
  }

  const confirmRel = (i) => setConfirmed(prev => new Set([...prev, i]))
  const rejectRel  = (i) => setRejected(prev  => new Set([...prev, i]))

  const commitExpert = () => {
    const cnt = confirmed.size
    msg(`已提交 ${cnt} 条关系至 RelOS 专家知识层`, 'var(--green)')
  }

  return (
    <div className="relos-page">
      {toast && <Toast key={toast.k} msg={toast.m} color={toast.c} />}

      <h2>
        专家知识采集
        <span className="layer-pill lp2">知识层 2 · Expert Knowledge</span>
      </h2>
      <p className="muted" style={{ marginBottom: 12 }}>
        通过结构化访谈引导专家将隐性经验转化为可计算的关系知识。系统根据回答自动生成候选关系，专家确认后写入图谱。
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
        {/* 场景选择 */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>选择访谈场景</h3>
          {SCENARIOS.map(sc => (
            <div
              key={sc.id}
              className="card"
              style={{
                cursor: 'pointer',
                marginBottom: 6,
                border: scenario?.id === sc.id ? '1.5px solid var(--blue)' : '0.5px solid var(--b1)',
                padding: '8px 12px',
              }}
              onClick={() => selectScenario(sc)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="badge b-purple">{sc.name}</span>
                <span className="muted" style={{ fontSize: 11 }}>{sc.qs.length} 个问题</span>
              </div>
            </div>
          ))}
        </div>

        {/* 专家信息 */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>专家信息</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
            <div>
              <div className="muted" style={{ marginBottom: 3 }}>姓名 / 职位</div>
              <input
                type="text"
                placeholder="如：张伟 / 高级维修工程师"
                value={expert.name}
                onChange={e => setExpert(p => ({ ...p, name: e.target.value }))}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <div className="muted" style={{ marginBottom: 3 }}>工作年限</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  type="range" min={1} max={30} value={expert.years}
                  onChange={e => setExpert(p => ({ ...p, years: +e.target.value }))}
                  style={{ flex: 1 }}
                />
                <span style={{ fontSize: 12, fontWeight: 500, minWidth: 32 }}>{expert.years}年</span>
              </div>
            </div>
            <div>
              <div className="muted" style={{ marginBottom: 3 }}>专业领域</div>
              <select
                value={expert.domain}
                onChange={e => setExpert(p => ({ ...p, domain: e.target.value }))}
                style={{ width: '100%' }}
              >
                {['机械维修', '电气控制', '工艺工程', '质量管理', '生产调度'].map(d => <option key={d}>{d}</option>)}
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* 访谈问答 */}
      <div className="card" style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: 0 }}>
            结构化访谈
            {scenario && <span style={{ color: 'var(--blue)', marginLeft: 6 }}>{scenario.name}</span>}
            {!scenario && <span style={{ color: 'var(--t3)', marginLeft: 6 }}>（请先选择场景）</span>}
          </h3>
          {scenario && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="muted">问题 {qIdx + 1} / {scenario.qs.length}</span>
              <button className="btn btn-p btn-sm" onClick={nextQ}>下一问题 →</button>
            </div>
          )}
        </div>
        {!scenario ? (
          <div className="qcard">
            <div className="q-num">请先选择左侧场景</div>
            <div className="q-text" style={{ color: 'var(--t2)' }}>选择访谈场景后，结构化问题将在此显示。</div>
          </div>
        ) : (
          <div className="qcard">
            <div className="q-num">问题 {qIdx + 1} / {scenario.qs.length}</div>
            <div className="q-text">{scenario.qs[qIdx].q}</div>
            <textarea
              value={ans}
              onChange={e => setAns(e.target.value)}
              placeholder={scenario.qs[qIdx].ph || '请用您自己的语言描述...'}
              rows={4}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
              <button className="btn btn-p btn-sm" onClick={submitAns}>提取关系 →</button>
            </div>
          </div>
        )}
      </div>

      {/* 候选关系 */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: 0 }}>
            从访谈提取的候选关系
            <span style={{ color: 'var(--blue)', marginLeft: 6 }}>{rels.length}</span> 条
          </h3>
          <button className="btn btn-ok btn-sm" onClick={commitExpert}>提交已确认关系</button>
        </div>
        {rels.length === 0 ? (
          <div className="muted" style={{ textAlign: 'center', padding: 16 }}>
            完成访谈后，系统将在此展示候选关系供您审核
          </div>
        ) : (
          rels.map((r, i) => (
            <div className="rrow" key={i} style={{ opacity: rejected.has(i) ? 0.4 : 1 }}>
              <span className="rnode" style={{ fontSize: 10 }}>{r.f}</span>
              <span style={{ fontSize: 10, color: 'var(--t2)' }}>→ {r.r} →</span>
              <span className="rnode" style={{ fontSize: 10 }}>{r.t}</span>
              <div className="cbar" style={{ flex: 1 }}>
                <div className={`cfill ${r.c >= 0.8 ? 'cf-high' : 'cf-mid'}`} style={{ width: `${r.c * 100}%` }} />
              </div>
              <span style={{ fontSize: 10, fontWeight: 500, minWidth: 28 }}>{r.c.toFixed(2)}</span>
              <span className="badge b-purple" style={{ fontSize: 9 }}>专家</span>
              {confirmed.has(i) ? (
                <span className="badge b-green">已确认</span>
              ) : rejected.has(i) ? (
                <span className="badge b-red">已拒绝</span>
              ) : (
                <>
                  <button className="btn btn-ok btn-sm" onClick={() => confirmRel(i)}>✓</button>
                  <button className="btn btn-no btn-sm" onClick={() => rejectRel(i)}>✗</button>
                </>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
