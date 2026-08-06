import { Navigate, Route, Routes } from 'react-router-dom'
import { AssessmentsPage } from './pages/AssessmentsPage'
import { CertificatesPage } from './pages/CertificatesPage'
import { CourseDetailPage } from './pages/CourseDetailPage'
import { CoursesPage } from './pages/CoursesPage'
import { DashboardPage } from './pages/DashboardPage'
import { ForcedPasswordResetPage } from './pages/ForcedPasswordResetPage'
import { LearnerReportsPage } from './pages/LearnerReportsPage'
import { LoginPage } from './pages/LoginPage'
import { AdminCourseListPage } from './pages/admin/AdminCourseListPage'
import { AdminSectionLayout } from './pages/admin/AdminSectionLayout'
import { BulkEnrollPage } from './pages/admin/BulkEnrollPage'
import { CertificateTemplatesPage } from './pages/admin/CertificateTemplatesPage'
import { CourseAnalyzeTab } from './pages/admin/CourseAnalyzeTab'
import { CourseCertificationTab } from './pages/admin/CourseCertificationTab'
import { CourseDashboardLayout } from './pages/admin/CourseDashboardLayout'
import { CourseDemoAccessTab } from './pages/admin/CourseDemoAccessTab'
import { CourseEditorPage } from './pages/admin/CourseEditorPage'
import { CourseShareTab } from './pages/admin/CourseShareTab'
import { CourseSlidesTab } from './pages/admin/CourseSlidesTab'
import { DemoUsersPage } from './pages/admin/DemoUsersPage'
import { GradingPage } from './pages/admin/GradingPage'
import { LearnersPage } from './pages/admin/LearnersPage'
import { OrganizationSettingsPage } from './pages/admin/OrganizationSettingsPage'
import { ReportsPage } from './pages/admin/ReportsPage'
import { AdminRoute } from './routes/AdminRoute'
import { AppLayout } from './routes/AppLayout'
import { OrgAdminRoute } from './routes/OrgAdminRoute'
import { ProtectedRoute } from './routes/ProtectedRoute'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/reset-password" element={<ForcedPasswordResetPage />} />

        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/courses" element={<CoursesPage />} />
          <Route path="/courses/:id" element={<CourseDetailPage />} />
          <Route path="/assessments" element={<AssessmentsPage />} />
          <Route path="/certificates" element={<CertificatesPage />} />
          <Route path="/reports" element={<LearnerReportsPage />} />

          <Route element={<AdminRoute />}>
            <Route path="/admin" element={<AdminSectionLayout />}>
              <Route index element={<Navigate to="courses" replace />} />
              <Route path="courses" element={<AdminCourseListPage />} />
              <Route path="courses/new" element={<CourseEditorPage />} />
              <Route path="grading" element={<GradingPage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="bulk-enroll" element={<BulkEnrollPage />} />
              <Route path="certificate-templates" element={<CertificateTemplatesPage />} />
              <Route path="demo-users" element={<DemoUsersPage />} />
            </Route>
            <Route path="/admin/learners" element={<LearnersPage />} />

            <Route path="/admin/courses/:slug" element={<CourseDashboardLayout />}>
              <Route index element={<Navigate to="slides" replace />} />
              <Route path="slides" element={<CourseSlidesTab />} />
              <Route path="settings" element={<CourseEditorPage />} />
              <Route path="certification" element={<CourseCertificationTab />} />
              <Route path="demo-access" element={<CourseDemoAccessTab />} />
              <Route path="share" element={<CourseShareTab />} />
              <Route path="analyze" element={<CourseAnalyzeTab />} />
            </Route>
          </Route>

          <Route element={<OrgAdminRoute />}>
            <Route path="/admin/organization" element={<OrganizationSettingsPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App
