/**
 * PublicKnowledge — 公开知识标注（原型 v2 · 知识层 1）
 * 从行业标准、学术文献、公开手册中抽取关系知识
 */
import { useState } from 'react'
import Toast from '../components/Toast'

const REL_TYPES = ['INDICATES', 'CAUSES', 'AFFECTS', 'BLOCKS', 'PRODUCES', 'DEPENDS_ON', 'OPERATES', 'DEPLETES']

const SAMPLES = {
  bearing: '当轴承出现过热症状时，通常由三种因素导致：润滑不足（占比约45%）、过载运行（约30%）、或安装偏差（约25%）。过热报警持续超过15分钟，应立即停机检查，否则可能导致轴承完全失效，造成设备停机并影响相关生产工单的完成时间。',
  quality: '注塑工艺中，熔体温度偏高是造成尺寸超差的首要因素，其次是保压压力不稳和模具温度波动。建议在工单开始前检查工艺参数是否在规格范围内，尤其是材料批次切换后应重新确认温度设定。',
  oee:     '设备综合效率（OEE）下降的三大原因：可用率损失（计划外停机）、性能损失（速度损失）和质量损失（不良品）。分析显示，过热报警引发的计划外停机是本季度可用率损失的主要贡献，平均每次停机造成0.8%的OEE下降。',
}

function highlight(text) {
  return text
    .replace(/(过热报警|振动报警|压力下降)/g, '<span class="ent-alarm">$1</span>')
    .replace(/(轴承磨损|轴承失效|安装偏差|润滑不足|尺寸超差)/g, '<span class="ent-issue">$1</span>')
    .replace(/(生产工单|工单|设备停机)/g, '<span class="ent-wo">$1</span>')
    .replace(/(注塑机|设备|机器|轴承)/g, '<span class="ent-machine">$1</span>')
}

export default function PublicKnowledge() {
  const [text, setText] = useState('')
  const [source, setSource] = useState('ISO 标准')
  const [selRel, setSelRel] = useState('INDICATES')
  const [preview, setPreview] = useState(null)
  const [rels, setRels] = useState([])
  const [toast, setToast] = useState(null)
  const msg = (m, c = 'var(--blue)') => setToast({ m, c, k: Date.now() })

  const autoExtract = () => {
    if (!text.trim()) { msg('请先输入或粘贴文本', 'var(--red)'); return }
    setPreview(highlight(text))
    setRels([
      { f: '过热报警', r: 'INDICATES', t: '轴承磨损',  c: 0.82, st: 'pending' },
      { f: '过热报警', r: 'AFFECTS',   t: '生产工单',  c: 0.71, st: 'pending' },
      { f: '轴承磨损', r: 'CAUSES',    t: '过热报警',  c: 0.88, st: 'pending' },
    ])
    msg('AI 预标注完成，请审核')
  }

  const relAct = (i, st) => {
    setRels(prev => prev.map((r, idx) => idx === i ? { ...r, st } : r))
    msg(st === 'ok' ? '已写入' : '已拒绝', st === 'ok' ? 'var(--green)' : 'var(--red)')
  }

  return (
    <div style={{ padding: '16px 20px' }}>
      {toast && <Toast key={toast.k} msg={toast.m} color={toast.c} />}

      <h2 className="page-h2">
        公开知识标注
        <span className="layer-pill lp1">知识层 1 · Public Knowledge</span>
      </h2>
      <p className="muted" style={{ marginBottom: 12 }}>
        从行业标准、学术文献、公开手册中抽取关系知识，构建领域通用本体基础层。
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
        {/* 文本输入 */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>输入文本片段</h3>
          <div style={{ display: 'flex', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
            {Object.entries({ bearing: '轴承故障', quality: '质量管控', oee: 'OEE分析' }).map(([k, v]) => (
              <button key={k} className="btn btn-sm" onClick={() => setText(SAMPLES[k])}>示例：{v}</button>
            ))}
          </div>
          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            rows={7}
            placeholder="粘贴或输入行业文献、标准手册文本..."
          />
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <select value={source} onChange={e => setSource(e.target.value)} style={{ flex: 1 }}>
              {['ISO 标准', '行业白皮书', '学术论文', '设备手册'].map(s => <option key={s}>{s}</option>)}
            </select>
            <button className="btn btn-p" onClick={autoExtract}>AI 预标注</button>
          </div>
        </div>

        {/* 实体类型图例 + 关系类型 */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>实体类型 · 颜色图例</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, fontSize: 12, marginBottom: 10 }}>
            {[
              { cls: 'ent-machine', label: 'Machine / 设备', desc: '物理设备实体' },
              { cls: 'ent-alarm',   label: 'Alarm / 报警',   desc: '故障信号类型' },
              { cls: 'ent-issue',   label: 'Issue / 问题',   desc: '根因/问题类型' },
              { cls: 'ent-wo',      label: 'WorkOrder / 工单', desc: '生产工单' },
            ].map(e => (
              <div key={e.cls} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className={e.cls}>{e.label}</span>
                <span className="muted">{e.desc}</span>
              </div>
            ))}
          </div>
          <div className="hdiv" />
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 6px' }}>关系类型选择</h3>
          <div>
            {REL_TYPES.map(r => (
              <span
                key={r}
                className={`chip ${selRel === r ? 'on' : ''}`}
                onClick={() => setSelRel(r)}
              >
                {r}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* 标注预览 & 提取关系 */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: 0 }}>标注预览 & 提取关系</h3>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn-ok btn-sm" onClick={() => msg('已提交至 RelOS 公开知识层', 'var(--green)')}>提交到图谱</button>
            <button className="btn btn-sm" onClick={() => { setText(''); setPreview(null); setRels([]) }}>清除</button>
          </div>
        </div>
        <div
          className="doc-chunk"
          style={{ minHeight: 60, color: preview ? 'var(--t1)' : 'var(--t3)' }}
          dangerouslySetInnerHTML={{ __html: preview || '点击「AI 预标注」后在此预览实体和关系...' }}
        />
        {rels.length > 0 && (
          <div style={{ marginTop: 8 }}>
            <h3 style={{ fontSize: 12, fontWeight: 500, marginBottom: 7 }}>AI 提取候选关系（请审核）</h3>
            {rels.map((r, i) => (
              <div key={i} className={`rel-pending ${r.st === 'ok' ? 'rel-ok' : r.st === 'no' ? 'rel-rej' : ''}`}>
                <span className="rnode">{r.f}</span>
                <span style={{ fontSize: 10, color: 'var(--t2)' }}>→ {r.r} →</span>
                <span className="rnode">{r.t}</span>
                <div style={{ flex: 1 }} />
                <span className={`badge ${r.c >= 0.8 ? 'b-blue' : 'b-amber'}`}>{r.c.toFixed(2)}</span>
                {r.st === 'pending' && <>
                  <button className="btn btn-ok btn-sm" onClick={() => relAct(i, 'ok')}>✓</button>
                  <button className="btn btn-no btn-sm" onClick={() => relAct(i, 'no')}>✗</button>
                </>}
                {r.st === 'ok' && <span className="badge b-green">已通过</span>}
                {r.st === 'no' && <span className="badge b-red">已拒绝</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
