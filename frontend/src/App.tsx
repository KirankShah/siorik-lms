import { Navigate, Route, Routes } from 'react-router-dom'
import { AchievementsPage } from './pages/AchievementsPage'
import { AssessmentsPage } from './pages/AssessmentsPage'
import { CertificatesPage } from './pages/CertificatesPage'
import { CourseDetailPage } from './pages/CourseDetailPage'
import { CoursesPage } from './pages/CoursesPage'
import { DashboardPage } from './pages/DashboardPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { LevelAssessmentPage } from './pages/LevelAssessmentPage'
import { LoginPage } from './pages/LoginPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { ResourcesPage } from './pages/ResourcesPage'
import { ResourceViewerPage } from './pages/ResourceViewerPage'
import { AdminCourseListPage } from './pages/admin/AdminCourseListPage'
import { AdminSectionLayout } from './pages/admin/AdminSectionLayout'
import { AnalyticsPage } from './pages/admin/AnalyticsPage'
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
import { LevelAssessmentPreviewPage } from './pages/admin/LevelAssessmentPreviewPage'
import { LevelQuestionsImportPage } from './pages/admin/LevelQuestionsImportPage'
import { QuestionBankPage } from './pages/admin/QuestionBankPage'
import { RoleBasedTrainingPage } from './pages/admin/RoleBasedTrainingPage'
import { StaffEnrollmentPage } from './pages/admin/StaffEnrollmentPage'
import { StaffTrainingReportPage } from './pages/admin/StaffTrainingReportPage'
import { OrganizationSettingsPage } from './pages/admin/OrganizationSettingsPage'
import { OrganizationsPage } from './pages/admin/OrganizationsPage'
import { ReportsPage } from './pages/admin/ReportsPage'
import { AdminRoute } from './routes/AdminRoute'
import { AppLayout } from './routes/AppLayout'
import { AssessmentsRoute } from './routes/AssessmentsRoute'
import { LevelAssessmentRoute } from './routes/LevelAssessmentRoute'
import { OrgAdminRoute } from './routes/OrgAdminRoute'
import { PlatformAdminRoute } from './routes/PlatformAdminRoute'
import { ProtectedRoute } from './routes/ProtectedRoute'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password/:uid/:token" element={<ResetPasswordPage />} />

      <Route element={<ProtectedRoute />}>
        {/* Outside AppLayout: a distraction-free full-bleed reader with no
            sidebar, opened in a new tab from ResourcesPage's "View" button —
            still requires auth via ProtectedRoute above. */}
        <Route path="/resources/:id/view" element={<ResourceViewerPage />} />

        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/courses" element={<CoursesPage />} />
          <Route path="/courses/:id" element={<CourseDetailPage />} />
          <Route element={<AssessmentsRoute />}>
            <Route path="/assessments" element={<AssessmentsPage />} />
          </Route>
          <Route element={<LevelAssessmentRoute />}>
            <Route path="/level-assessment" element={<LevelAssessmentPage />} />
          </Route>
          <Route path="/achievements" element={<AchievementsPage />} />
          <Route path="/certificates" element={<CertificatesPage />} />
          <Route path="/resources" element={<ResourcesPage />} />

          <Route element={<AdminRoute />}>
            <Route path="/admin" element={<AdminSectionLayout />}>
              <Route index element={<Navigate to="courses" replace />} />
              <Route path="courses" element={<AdminCourseListPage />} />
              <Route path="courses/new" element={<CourseEditorPage />} />
              <Route path="grading" element={<GradingPage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="analytics" element={<AnalyticsPage />} />
              <Route path="bulk-enroll" element={<BulkEnrollPage />} />
              <Route path="certificate-templates" element={<CertificateTemplatesPage />} />
              <Route path="demo-users" element={<DemoUsersPage />} />
              <Route path="assessment-questions" element={<LevelQuestionsImportPage />} />
            </Route>

            <Route path="/admin/question-bank" element={<QuestionBankPage />} />
            <Route path="/admin/level-assessment-preview/:levelId" element={<LevelAssessmentPreviewPage />} />

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
            <Route path="/admin/staff-enrollment" element={<StaffEnrollmentPage />} />
            <Route path="/admin/staff-training-report" element={<StaffTrainingReportPage />} />
            <Route path="/admin/role-based-training" element={<RoleBasedTrainingPage />} />
          </Route>

          <Route element={<PlatformAdminRoute />}>
            <Route path="/admin/organizations" element={<OrganizationsPage />} />
            {/* Moved out of the OrgAdminRoute block above — Learners is now
                platform-admin-only, unlike its Staff Enrollment/Staff
                Training Report/Organization Settings siblings. */}
            <Route path="/admin/learners" element={<LearnersPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App
