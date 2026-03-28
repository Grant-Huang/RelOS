/**
 * 专家知识（层 2）：访谈微卡片 + 结构化录入向导
 */
import { useSearchParams } from 'react-router-dom'
import { UserCog } from 'lucide-react'
import LayerAuthorityBar from '../../components/LayerAuthorityBar'
import Interview from '../Interview'
import ExpertInit from '../ExpertInit'

export default function KnowledgeExpert() {
  const [sp, setSp] = useSearchParams()
  const tab = sp.get('tab') === 'wizard' ? 'wizard' : 'interview'

  const setTab = (t) => {
    const next = new URLSearchParams(sp)
    next.set('tab', t)
    setSp(next, { replace: true })
  }

  return (
    <div className="wb-main p-4 md:p-8 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-4">
        <UserCog className="w-7 h-7 flex-shrink-0" style={{ color: 'var(--wb-purple)' }} />
        <div>
          <h1 className="text-xl md:text-2xl font-semibold" style={{ color: 'var(--wb-text)' }}>
            专家知识采集
          </h1>
          <p className="text-sm wb-text-muted">层 2 · 访谈确认与结构化录入</p>
        </div>
      </div>

      <LayerAuthorityBar layer={2} />

      <div
        className="flex gap-1 mb-6 border-b pb-px"
        style={{ borderColor: 'var(--wb-border)' }}
        role="tablist"
      >
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'interview'}
          onClick={() => setTab('interview')}
          className={`px-4 py-2.5 text-sm font-medium rounded-t-lg min-h-[44px] transition-colors ${
            tab === 'interview'
              ? 'text-[color:var(--wb-blue)] border-b-2 border-[color:var(--wb-blue)] -mb-px'
              : 'wb-text-muted hover:wb-text-secondary'
          }`}
        >
          访谈微卡片
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'wizard'}
          onClick={() => setTab('wizard')}
          className={`px-4 py-2.5 text-sm font-medium rounded-t-lg min-h-[44px] transition-colors ${
            tab === 'wizard'
              ? 'text-[color:var(--wb-blue)] border-b-2 border-[color:var(--wb-blue)] -mb-px'
              : 'wb-text-muted hover:wb-text-secondary'
          }`}
        >
          结构化录入
        </button>
      </div>

      <div role="tabpanel">
        {tab === 'interview' ? <Interview embedded /> : <ExpertInit embedded />}
      </div>
    </div>
  )
}
