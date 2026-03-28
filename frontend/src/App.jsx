import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import AlarmAnalysis from './pages/AlarmAnalysis'
import LineEfficiency from './pages/LineEfficiency'
import StrategicSim from './pages/StrategicSim'
import RuntimeDashboard from './pages/runtime/RuntimeDashboard'
import AutomationMonitor from './pages/runtime/AutomationMonitor'
import PromptLabeling from './pages/runtime/PromptLabeling'
import KnowledgePublic from './pages/knowledge/KnowledgePublic'
import KnowledgeExpert from './pages/knowledge/KnowledgeExpert'
import KnowledgeDocuments from './pages/knowledge/KnowledgeDocuments'
import KbStatus from './pages/system/KbStatus'

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
        <Route path="/system/kb-status" element={<KbStatus />} />
        <Route path="/alarm" element={<AlarmAnalysis />} />
        <Route path="/line-efficiency" element={<LineEfficiency />} />
        <Route path="/strategic-sim" element={<StrategicSim />} />
        <Route path="/hitl" element={<Navigate to="/runtime/prompt" replace />} />
        <Route path="/expert-init" element={<Navigate to="/knowledge/expert?tab=wizard" replace />} />
        <Route path="/interview" element={<Navigate to="/knowledge/expert?tab=interview" replace />} />
        <Route path="/dashboard" element={<Navigate to="/runtime/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/runtime/dashboard" replace />} />
      </Routes>
    </Layout>
  )
}
