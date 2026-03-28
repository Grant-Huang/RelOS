/**
 * 知识层权威性说明：置信度上限与典型来源（全局 relos 令牌）
 */
const LAYERS = {
  1: {
    title: '知识层 1 · 公开知识',
    phase: 'bootstrap',
    maxLabel: 'AI 预标注上限 0.85',
    detail: '行业标准、文献、公开手册；需人工审核后方可强化。',
    pillClass: 'lp1',
  },
  2: {
    title: '知识层 2 · 专家知识',
    phase: 'interview',
    maxLabel: '专家确认后可达 1.0',
    detail: '结构化访谈与微卡片确认；隐性经验显式化，不可替代为纯文档流。',
    pillClass: 'lp2',
  },
  3: {
    title: '知识层 3 · 企业文档',
    phase: 'pretrain',
    maxLabel: 'LLM 预标注上限 0.85',
    detail: 'SOP、维修记录、FMEA 等；批审效率优先，默认待审核。',
    pillClass: 'lp3',
  },
}

export default function LayerAuthorityBar({ layer = 1 }) {
  const cfg = LAYERS[layer] || LAYERS[1]
  return (
    <div className="relos-layer-bar">
      <div className="relos-layer-head">
        <span className={`layer-pill ${cfg.pillClass}`}>{cfg.title}</span>
        <span className="relos-layer-meta">{cfg.maxLabel}</span>
      </div>
      <p className="relos-layer-detail">
        <code className="relos-code">knowledge_phase={cfg.phase}</code>
        {' · '}
        {cfg.detail}
      </p>
    </div>
  )
}
