import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { isAuthenticated } from './api'
import Layout from './components/Layout'
import Login from './components/Login'
import Dashboard from './components/Dashboard'
import IpList from './components/IpList'
import IpDetail from './components/IpDetail'
import GroupManager from './components/GroupManager'
import ScanTrigger from './components/ScanTrigger'
import Import from './components/Import'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="ips" element={<IpList />} />
          <Route path="ips/:ip" element={<IpDetail />} />
          <Route path="groups" element={<GroupManager />} />
          <Route path="scan" element={<ScanTrigger />} />
          <Route path="import" element={<Import />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
