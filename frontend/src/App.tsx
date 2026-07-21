import { Navigate, Route, Routes } from 'react-router-dom'
import { CertificatesPage } from './pages/CertificatesPage'
import { CourseDetailPage } from './pages/CourseDetailPage'
import { CoursesPage } from './pages/CoursesPage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { AppLayout } from './routes/AppLayout'
import { ProtectedRoute } from './routes/ProtectedRoute'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/courses" element={<CoursesPage />} />
          <Route path="/courses/:id" element={<CourseDetailPage />} />
          <Route path="/certificates" element={<CertificatesPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App
