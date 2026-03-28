import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'

import RuntimeDashboard from './pages/runtime/RuntimeDashboard'
import AutomationMonitor from './pages/runtime/AutomationMonitor'
import PromptLabeling from './pages/runtime/PromptLabeling'

import KnowledgePublic from './pages/knowledge/KnowledgePublic'
import KnowledgeExpert from './pages/knowledge/KnowledgeExpert'
import KnowledgeDocuments from './pages/knowledge/KnowledgeDocuments'

import SystemKbStatus from './pages/system/KbStatus'

import AlarmAnalysis from './pages/AlarmAnalysis'
import LineEfficiency from './pages/LineEfficiency'
import StrategicSim from './pages/StrategicSim'

/** 旧路径页面，仅用于兼容书签 */
import AutoAnnotation from './pages/AutoAnnotation'
import HITLQueue from './pages/HITLQueue'
import PublicKnowledge from './pages/PublicKnowledge'
import ExpertKnowledge from './pages/ExpertKnowledge'
import DocAnnotation from './pages/DocAnnotation'
import KBStatus from './pages/KBStatus'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/runtime/dashboard" replace />} />

        <Route path="/runtime/dashboard" element={<RuntimeDashboard />} />
        <Route path="/runtime/automation" element={<AutomationMonitor />} />
        <Route path="/runtime/prompt" element={<PromptLabeling />} />

        <Route path="/knowledge/public" element={<KnowledgePublic />} />
        <Route path="/knowledge/expert" element={<KnowledgeExpert />} />
        <Route path="/knowledge/documents" element={<KnowledgeDocuments />} />

        <Route path="/system/kb-status" element={<SystemKbStatus />} />

        <Route path="/alarm" element={<AlarmAnalysis />} />
        <Route path="/line-efficiency" element={<LineEfficiency />} />
        <Route path="/strategic-sim" element={<StrategicSim />} />

        <Route path="/auto-annotation" element={<Navigate to="/runtime/automation" replace />} />
        <Route path="/hitl" element={<Navigate to="/runtime/prompt" replace />} />
        <Route path="/public-knowledge" element={<Navigate to="/knowledge/public" replace />} />
        <Route path="/expert-knowledge" element={<Navigate to="/knowledge/expert" replace />} />
        <Route path="/doc-annotation" element={<Navigate to="/knowledge/documents" replace />} />
        <Route path="/kb-status" element={<Navigate to="/system/kb-status" replace />} />

        <Route path="/legacy/auto-annotation" element={<AutoAnnotation />} />
        <Route path="/legacy/hitl" element={<HITLQueue />} />
        <Route path="/legacy/public-knowledge" element={<PublicKnowledge />} />
        <Route path="/legacy/expert-knowledge" element={<ExpertKnowledge />} />
        <Route path="/legacy/doc-annotation" element={<DocAnnotation />} />
        <Route path="/legacy/kb-status" element={<KBStatus />} />

        <Route path="*" element={<Navigate to="/runtime/dashboard" replace />} />
      </Routes>
    </Layout>
  )
}
