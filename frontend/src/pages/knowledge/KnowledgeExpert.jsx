/**
 * 专家知识采集 — 对齐 docs/relos_workbench_v2.html #v-kb-expert
 * 引导式访谈（原型）+ 可选：后端微卡片 API、结构化录入向导
 */
import { useSearchParams } from 'react-router-dom'
import { useState } from 'react'
import Interview from '../Interview'
import ExpertInit from '../ExpertInit'

const SCENARIOS = [
  {
    id: 0,
    name: '设备故障分析',
    qs: [
      {
        q: '在您的经验中，过热报警最常见的根本原因是什么？请列举前3位。',
        ph: '例如：轴承磨损、冷却液不足、转速过高...',
      },
      {
        q: '哪些设备特征（型号、使用年限、工况）会影响故障发生概率？',
        ph: '例如：老设备轴承故障率更高，高负载工况下冷却问题更常见...',
      },
      {
        q: '遇到过热报警后，您的标准处置步骤是什么？有哪些关键判断节点？',
        ph: '例如：先确认温度数值，超过85°C立即停机；再检查冷却液，水位低于标线则补液...',
      },
    ],
  },
  {
    id: 1,
    name: '工单延误分析',
    qs: [
      { q: '工单延误最常见的直接原因有哪些？设备问题、物料短缺还是人员问题？', ph: '' },
      { q: '哪类设备停机对工单影响最大？', ph: '' },
      { q: '您如何在工单开始前预判延误风险？', ph: '' },
    ],
  },
  {
    id: 2,
    name: '质量异常分析',
    qs: [
      { q: '这类缺陷最可能出现在哪个工序？有无规律性？', ph: '' },
      { q: '物料批次与质量异常有关联吗？如何判断？', ph: '' },
      { q: '操作员技能水平对质量有多大影响？哪些操作最容易出错？', ph: '' },
    ],
  },
]

const SAMPLE_RELS_PER_ANSWER = [
  [
    { f: '过热报警', r: 'INDICATES', t: '轴承磨损', c: 0.82 },
    { f: '轴承磨损', r: 'CAUSES', t: '设备停机', c: 0.75 },
  ],
  [
    { f: '设备停机', r: 'AFFECTS', t: '生产工单', c: 0.88 },
    { f: '过热报警', r: 'INDICATES', t: '冷却液不足', c: 0.63 },
  ],
  [
    { f: '轴承磨损', r: 'INDICATES', t: '过热报警', c: 0.79 },
    { f: '过热报警', r: 'BLOCKS', t: 'Production', c: 0.84 },
  ],
]

export default function KnowledgeExpert() {
  const [sp, setSp] = useSearchParams()
  const tab = sp.get('tab')
  const mode = tab === 'wizard' ? 'wizard' : tab === 'interview' ? 'api' : 'guide'

  const setMode = (m) => {
    const next = new URLSearchParams(sp)
    if (m === 'guide') next.delete('tab')
    else if (m === 'api') next.set('tab', 'interview')
    else next.set('tab', 'wizard')
    setSp(next, { replace: true })
  }

  const [scenario, setScenario] = useState(null)
  const [qIdx, setQIdx] = useState(0)
  const [expAns, setExpAns] = useState('')
  const [expRels, setExpRels] = useState([])
  const [expertName, setExpertName] = useState('')
  const [years, setYears] = useState(10)
  const [domain, setDomain] = useState('机械维修')

  const selectScenario = (s) => {
    setScenario(s)
    setQIdx(0)
    setExpAns('')
    setExpRels([])
  }

  const currentQ = scenario?.qs[qIdx]

  const submitAnswer = () => {
    if (!scenario) return
    if (!expAns || expAns.trim().length < 5) {
      window.alert('请填写回答后再提取')
      return
    }
    const newRels = SAMPLE_RELS_PER_ANSWER[qIdx % SAMPLE_RELS_PER_ANSWER.length]
    setExpRels((prev) => [...prev, ...newRels])
    setExpAns('')
    if (qIdx < scenario.qs.length - 1) {
      setQIdx((i) => i + 1)
    } else {
      window.alert('所有问题已完成！请审核下方候选关系。')
    }
  }

  const nextQOnly = () => {
    if (!scenario) {
      window.alert('请先选择场景')
      return
    }
    if (qIdx < scenario.qs.length - 1) {
      setQIdx((i) => i + 1)
      setExpAns('')
    } else {
      window.alert('已是最后一题')
    }
  }

  const removeRel = (i) => {
    setExpRels((prev) => prev.filter((_, idx) => idx !== i))
  }

  const chipCls = (m) => `chip${mode === m ? ' on' : ''}`

  return (
    <div className="relos-page">
      <h2>
        专家知识采集 <span className="layer-pill lp2">知识层 2 · Expert Knowledge</span>
      </h2>
      <div className="muted mb12">
        通过结构化访谈引导专家将隐性经验转化为可计算的关系知识。系统根据回答自动生成候选关系，专家确认后写入图谱。
      </div>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
        <span role="button" tabIndex={0} className={chipCls('guide')} onClick={() => setMode('guide')} onKeyDown={(e) => e.key === 'Enter' && setMode('guide')}>
          引导式访谈
        </span>
        <span role="button" tabIndex={0} className={chipCls('api')} onClick={() => setMode('api')} onKeyDown={(e) => e.key === 'Enter' && setMode('api')}>
          后端微卡片
        </span>
        <span role="button" tabIndex={0} className={chipCls('wizard')} onClick={() => setMode('wizard')} onKeyDown={(e) => e.key === 'Enter' && setMode('wizard')}>
          结构化录入
        </span>
      </div>

      {mode === 'api' && (
        <div className="card mb10">
          <h3>RelOS 访谈会话（API）</h3>
          <p className="muted" style={{ marginBottom: 10 }}>
            与后端会话接口对接的微卡片流；与上方引导式原型相互独立。
          </p>
          <Interview embedded workbench />
        </div>
      )}

      {mode === 'wizard' && (
        <div className="card mb10">
          <h3>结构化录入向导</h3>
          <p className="muted" style={{ marginBottom: 10 }}>
            分步录入设备与关系并调用 expert-init 等接口。
          </p>
          <ExpertInit embedded />
        </div>
      )}

      {mode === 'guide' && (
        <>
          <div className="g2 mb12">
            <div className="card">
              <h3>选择访谈场景</h3>
              <div id="exp-scenarios" style={{ marginTop: 8 }}>
                {SCENARIOS.map((s) => (
                  <div
                    key={s.id}
                    id={`es${s.id}`}
                    className="card"
                    style={{
                      cursor: 'pointer',
                      marginBottom: 6,
                      border: scenario?.id === s.id ? '1.5px solid var(--blue)' : '1.5px solid transparent',
                      transition: 'border-color 0.15s',
                      padding: '10px 12px',
                    }}
                    role="button"
                    tabIndex={0}
                    onClick={() => selectScenario(s)}
                    onKeyDown={(e) => e.key === 'Enter' && selectScenario(s)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="badge b-purple">{s.name}</span>
                      <span className="muted" style={{ fontSize: 11 }}>
                        {s.qs.length} 个问题
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="card">
              <h3>专家信息</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
                <div>
                  <div className="muted" style={{ marginBottom: 3 }}>
                    姓名 / 职位
                  </div>
                  <input
                    type="text"
                    value={expertName}
                    onChange={(e) => setExpertName(e.target.value)}
                    placeholder="如：张伟 / 高级维修工程师"
                    style={{ width: '100%' }}
                  />
                </div>
                <div>
                  <div className="muted" style={{ marginBottom: 3 }}>
                    工作年限
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <input type="range" min={1} max={30} value={years} onChange={(e) => setYears(Number(e.target.value))} style={{ flex: 1 }} />
                    <span style={{ fontSize: 12, fontWeight: 500, minWidth: 36 }}>{years}年</span>
                  </div>
                </div>
                <div>
                  <div className="muted" style={{ marginBottom: 3 }}>
                    专业领域
                  </div>
                  <select value={domain} onChange={(e) => setDomain(e.target.value)} style={{ width: '100%' }}>
                    <option>机械维修</option>
                    <option>电气控制</option>
                    <option>工艺工程</option>
                    <option>质量管理</option>
                    <option>生产调度</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          <div className="card mb10">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <h3 style={{ marginBottom: 0 }}>
                结构化访谈{' '}
                <span id="exp-sc-name" style={{ color: 'var(--blue)' }}>
                  {scenario ? `（${scenario.name}）` : '（请先选择场景）'}
                </span>
              </h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="muted">
                  问题 <span id="q-cur">{scenario ? qIdx + 1 : 1}</span> / <span id="q-tot">{scenario ? scenario.qs.length : 3}</span>
                </span>
                <button type="button" className="btn btn-sm btn-p" onClick={nextQOnly}>
                  下一问题 →
                </button>
              </div>
            </div>
            <div id="interview-q">
              {!scenario ? (
                <div className="qcard">
                  <div className="q-num">请先选择左侧场景</div>
                  <div className="q-text">选择访谈场景后，结构化问题将在此显示。</div>
                </div>
              ) : (
                <div className="qcard">
                  <div className="q-num">
                    问题 {qIdx + 1} / {scenario.qs.length}
                  </div>
                  <div className="q-text">{currentQ.q}</div>
                  <textarea value={expAns} onChange={(e) => setExpAns(e.target.value)} placeholder={currentQ.ph || '请用您自己的语言描述...'} rows={4} />
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
                    <button type="button" className="btn btn-p btn-sm" onClick={submitAnswer}>
                      提取关系 →
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <h3 style={{ marginBottom: 0 }}>
                从访谈提取的候选关系 <span style={{ color: 'var(--blue)' }}>{expRels.length}</span> 条
              </h3>
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  type="button"
                  className="btn btn-sm btn-ok"
                  onClick={() => window.alert(`将提交 ${expRels.length} 条至专家知识层（演示）；接入写入 API 后可落库。`)}
                >
                  提交已确认关系
                </button>
              </div>
            </div>
            <div id="exp-rels">
              {expRels.length === 0 ? (
                <div className="muted" style={{ textAlign: 'center', padding: 16 }}>
                  完成访谈后，系统将在此展示候选关系供您审核
                </div>
              ) : (
                expRels.map((r, i) => (
                  <div key={`${r.f}-${r.r}-${r.t}-${i}`} className="rrow">
                    <span className="rnode" style={{ fontSize: 10 }}>
                      {r.f}
                    </span>
                    <span style={{ fontSize: 10, color: 'var(--t2)' }}>→ {r.r} →</span>
                    <span className="rnode" style={{ fontSize: 10 }}>
                      {r.t}
                    </span>
                    <div className="cbar" style={{ flex: 1 }}>
                      <div className={`cfill ${r.c >= 0.8 ? 'cf-high' : 'cf-mid'}`} style={{ width: `${r.c * 100}%` }} />
                    </div>
                    <span style={{ fontSize: 10, fontWeight: 500, minWidth: 28 }}>{r.c.toFixed(2)}</span>
                    <span className="badge b-purple" style={{ fontSize: 9 }}>
                      专家
                    </span>
                    <button type="button" className="btn btn-ok btn-sm" onClick={() => window.alert('已标记确认（演示）')}>
                      ✓
                    </button>
                    <button type="button" className="btn btn-no btn-sm" onClick={() => removeRel(i)}>
                      ✗
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
