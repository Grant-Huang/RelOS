import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AlarmAnalysis from './pages/AlarmAnalysis'
import HITLQueue from './pages/HITLQueue'
import ExpertInit from './pages/ExpertInit'
import LineEfficiency from './pages/LineEfficiency'
import StrategicSim from './pages/StrategicSim'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/alarm" element={<AlarmAnalysis />} />
        <Route path="/hitl" element={<HITLQueue />} />
        <Route path="/expert-init" element={<ExpertInit />} />
        <Route path="/line-efficiency" element={<LineEfficiency />} />
        <Route path="/strategic-sim" element={<StrategicSim />} />
      </Routes>
    </Layout>
  )
}
