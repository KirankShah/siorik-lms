import { Navigate, Route, Routes } from 'react-router-dom'
import { CertificatesPage } from './pages/CertificatesPage'
import { CourseDetailPage } from './pages/CourseDetailPage'
import { CoursesPage } from './pages/CoursesPage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { AdminCourseListPage } from './pages/admin/AdminCourseListPage'
import { AdminSectionLayout } from './pages/admin/AdminSectionLayout'
import { BulkEnrollPage } from './pages/admin/BulkEnrollPage'
import { CourseContentBuilderPage } from './pages/admin/CourseContentBuilderPage'
import { CourseEditorPage } from './pages/admin/CourseEditorPage'
import { GradingPage } from './pages/admin/GradingPage'
import { PageEditorPage } from './pages/admin/PageEditorPage'
import { ReportsPage } from './pages/admin/ReportsPage'
import { AdminRoute } from './routes/AdminRoute'
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

          <Route element={<AdminRoute />}>
            <Route path="/admin" element={<AdminSectionLayout />}>
              <Route index element={<Navigate to="courses" replace />} />
              <Route path="courses" element={<AdminCourseListPage />} />
              <Route path="courses/new" element={<CourseEditorPage />} />
              <Route path="courses/:slug/edit" element={<CourseEditorPage />} />
              <Route path="courses/:slug/content" element={<CourseContentBuilderPage />} />
              <Route path="pages/:pageId" element={<PageEditorPage />} />
              <Route path="grading" element={<GradingPage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="bulk-enroll" element={<BulkEnrollPage />} />
            </Route>
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App
