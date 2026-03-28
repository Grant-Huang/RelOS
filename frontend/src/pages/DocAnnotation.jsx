/**
 * DocAnnotation — 企业文档标注（原型 v2 · 知识层 3）
 * 上传企业内部文档，LLM 预标注后人工审核
 */
import { useState } from 'react'
import Toast from '../components/Toast'

const INIT_DOCS = [
  { name: '设备说明书_M1.pdf',  st: 'done',       total: 28, approved: 23 },
  { name: '故障代码手册_V3.pdf', st: 'processing', total: 0,  approved: 0  },
  { name: 'SOP_焊接工艺.docx',  st: 'queued',     total: 0,  approved: 0  },
  { name: 'FMEA_注塑线.xlsx',   st: 'queued',     total: 0,  approved: 0  },
]

const INIT_DOC_RELS = [
  { f: '过热报警',  r: 'INDICATES', t: '轴承磨损',  c: 0.91, ctx: '高温环境', st: 'pending'  },
  { f: '过热报警',  r: 'INDICATES', t: '冷却液不足', c: 0.74, ctx: '通用',    st: 'pending'  },
  { f: '振动报警',  r: 'INDICATES', t: '轴承磨损',  c: 0.89, ctx: '通用',    st: 'approved' },
  { f: '轴承磨损',  r: 'CAUSES',    t: '过热报警',  c: 0.85, ctx: '通用',    st: 'pending'  },
  { f: '维修工单',  r: 'AFFECTS',   t: '生产工单',  c: 0.78, ctx: '通用',    st: 'rejected' },
]

const ST_DOT = { done: 's-on', processing: 's-mid', queued: 's-off' }

export default function DocAnnotation() {
  const [docs, setDocs] = useState(INIT_DOCS)
  const [docRels, setDocRels] = useState(INIT_DOC_RELS)
  const [activeDoc, setActiveDoc] = useState('设备说明书_M1.pdf')
  const [toast, setToast] = useState(null)
  const msg = (m, c = 'var(--blue)') => setToast({ m, c, k: Date.now() })

  const relAct = (i, st) => {
    setDocRels(prev => prev.map((r, idx) => idx === i ? { ...r, st } : r))
    msg(st === 'approved' ? '已确认写入图谱' : '已拒绝', st === 'approved' ? 'var(--green)' : 'var(--red)')
  }

  const batchApprove = () => {
    setDocRels(prev => prev.map(r => r.st === 'pending' ? { ...r, st: 'approved' } : r))
    msg('批量审核通过', 'var(--green)')
  }

  const simUpload = () => {
    const names = ['维修记录_Q1.xlsx', '工艺规程_铸造.pdf', '质量报告_2025.docx']
    const name = names[Math.floor(Math.random() * names.length)]
    setDocs(prev => [...prev, { name, st: 'queued', total: 0, approved: 0 }])
    msg('已上传：' + name)
  }

  const pending = docRels.filter(r => r.st === 'pending')
  const approved = docRels.filter(r => r.st === 'approved')
  const rejected = docRels.filter(r => r.st === 'rejected')

  return (
    <div className="relos-page">
      {toast && <Toast key={toast.k} msg={toast.m} color={toast.c} />}

      <h2>
        企业文档标注
        <span className="layer-pill lp3">知识层 3 · Enterprise Docs</span>
      </h2>
      <p className="muted" style={{ marginBottom: 12 }}>
        上传企业内部文档（SOP、维修记录、FMEA、工艺规程），系统 LLM 预标注后由人工审核确认，确保知识准确性。
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
        {/* 文档队列 */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>文档队列</h3>
          {docs.map((d, i) => (
            <div
              key={i}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '7px 0', borderBottom: '0.5px solid var(--b1)',
                fontSize: 12, cursor: 'pointer',
              }}
              onClick={() => { setActiveDoc(d.name); msg('已加载：' + d.name) }}
            >
              <span className={`sdot ${ST_DOT[d.st]}`} />
              <div style={{ flex: 1, fontWeight: d.st === 'done' ? 500 : 400 }}>{d.name}</div>
              <span className="muted">
                {d.st === 'done' ? `${d.total}条/${d.approved}已审` : d.st === 'processing' ? '处理中' : '排队'}
              </span>
            </div>
          ))}
          <div className="upz" style={{ marginTop: 8 }} onClick={simUpload}>
            <div style={{ fontSize: 18, marginBottom: 6, color: 'var(--t3)' }}>↑</div>
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--t1)' }}>点击上传企业文档</div>
            <div className="muted" style={{ marginTop: 4 }}>支持 PDF · Word · Excel · TXT</div>
          </div>
        </div>

        {/* 预标注统计 */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: '0 0 8px' }}>预标注处理统计</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <div className="stat"><div className="stat-v" style={{ color: 'var(--blue)' }}>5</div><div className="stat-l">已处理文档</div></div>
            <div className="stat"><div className="stat-v" style={{ color: 'var(--amber)' }}>{pending.length}</div><div className="stat-l">待审核关系</div></div>
            <div className="stat"><div className="stat-v" style={{ color: 'var(--green)' }}>{approved.length}</div><div className="stat-l">已确认关系</div></div>
            <div className="stat"><div className="stat-v" style={{ color: 'var(--red)' }}>{rejected.length}</div><div className="stat-l">已拒绝关系</div></div>
          </div>
          <div className="hdiv" />
          <div style={{ fontSize: 11, color: 'var(--t2)', lineHeight: 1.7 }}>
            LLM 预标注准确率（基于已审核）：<strong style={{ color: 'var(--green)' }}>88.9%</strong><br />
            平均每文档耗时：<strong>约 2.5 分钟</strong>人工审核<br />
            最多被拒原因：关系方向错误（7次），错误实体类型（4次）
          </div>
        </div>
      </div>

      {/* 文档标注工作区 */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <h3 style={{ fontSize: 12, fontWeight: 500, margin: 0 }}>
            标注工作区 · <span style={{ color: 'var(--blue)' }}>{activeDoc}</span>
          </h3>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn-ok btn-sm" onClick={batchApprove}>批量通过</button>
            <button className="btn btn-p btn-sm" onClick={() => msg('已提交已审核关系至 RelOS 企业知识层', 'var(--green)')}>提交已审核</button>
          </div>
        </div>

        {/* 文档预览带实体高亮 */}
        <div className="doc-chunk" style={{ marginBottom: 8 }}>
          当 <span className="ent-machine" onClick={() => msg('已选中：1号注塑机')}>1号注塑机</span> 发生{' '}
          <span className="ent-alarm" onClick={() => msg('已选中：过热报警')}>过热报警</span> 时，最常见的根本原因是{' '}
          <span className="ent-issue" onClick={() => msg('已选中：轴承磨损')}>轴承磨损</span>，尤其在环境温度高于 35°C 的条件下。
          处理步骤包括：立即降低 <span className="ent-machine" onClick={() => msg('已选中：1号注塑机')}>1号注塑机</span> 转速，
          检查 <span className="ent-issue" onClick={() => msg('已选中：冷却液水位')}>冷却液水位</span>，
          并通知维修班组创建 <span className="ent-wo" onClick={() => msg('已选中：维修工单')}>维修工单</span>。
        </div>
        <div className="doc-chunk" style={{ marginBottom: 8 }}>
          历史数据表明，<span className="ent-alarm" onClick={() => msg('已选中：振动报警')}>振动报警</span> 与{' '}
          <span className="ent-issue" onClick={() => msg('已选中：轴承磨损')}>轴承磨损</span> 的关联度达到 91%，
          建议在 <span className="ent-alarm" onClick={() => msg('已选中：振动报警')}>振动报警</span> 出现后 30 分钟内完成轴承检查，
          否则可能导致 <span className="ent-wo" onClick={() => msg('已选中：生产工单')}>生产工单</span> 延误。
        </div>

        {/* LLM 预标注关系 */}
        <h3 style={{ fontSize: 12, fontWeight: 500, marginBottom: 7 }}>LLM 预标注关系 · 待审核</h3>
        {docRels.map((r, i) => (
          <div key={i} className={`rel-pending ${r.st === 'approved' ? 'rel-ok' : r.st === 'rejected' ? 'rel-rej' : ''}`}>
            <span className="rnode" style={{ fontSize: 10 }}>{r.f}</span>
            <span style={{ fontSize: 10, color: 'var(--t2)' }}>→ {r.r} →</span>
            <span className="rnode" style={{ fontSize: 10 }}>{r.t}</span>
            <span className="badge b-gray" style={{ fontSize: 9 }}>{r.ctx}</span>
            <div className="cbar" style={{ flex: 1, maxWidth: 60 }}>
              <div className={`cfill ${r.c >= 0.8 ? 'cf-high' : 'cf-mid'}`} style={{ width: `${r.c * 100}%` }} />
            </div>
            <span style={{ fontSize: 10, minWidth: 28 }}>{r.c.toFixed(2)}</span>
            {r.st === 'pending' && (
              <>
                <button className="btn btn-ok btn-sm" onClick={() => relAct(i, 'approved')}>✓</button>
                <button className="btn btn-no btn-sm" onClick={() => relAct(i, 'rejected')}>✗</button>
                <button className="btn btn-sm" style={{ fontSize: 10 }} onClick={() => msg('修改功能开发中')}>✎</button>
              </>
            )}
            {r.st === 'approved' && <span className="badge b-green">已通过</span>}
            {r.st === 'rejected' && <span className="badge b-red">已拒绝</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
