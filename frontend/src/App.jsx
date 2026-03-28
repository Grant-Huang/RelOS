import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard       from './pages/Dashboard'
import AutoAnnotation  from './pages/AutoAnnotation'
import HITLQueue       from './pages/HITLQueue'
import PublicKnowledge from './pages/PublicKnowledge'
import ExpertKnowledge from './pages/ExpertKnowledge'
import DocAnnotation   from './pages/DocAnnotation'
import KBStatus        from './pages/KBStatus'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/"                 element={<Dashboard />} />
        <Route path="/auto-annotation"  element={<AutoAnnotation />} />
        <Route path="/hitl"             element={<HITLQueue />} />
        <Route path="/public-knowledge" element={<PublicKnowledge />} />
        <Route path="/expert-knowledge" element={<ExpertKnowledge />} />
        <Route path="/doc-annotation"   element={<DocAnnotation />} />
        <Route path="/kb-status"        element={<KBStatus />} />
      </Routes>
    </Layout>
  )
}
