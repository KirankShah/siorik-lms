import { useEffect, useState } from 'react'
import { Award, BookOpen, CalendarClock, ClipboardList, Users } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { BadgesWidget } from '../components/BadgesWidget'
import { LeaderboardWidget } from '../components/LeaderboardWidget'
import { LearnerWelcomeBanner } from '../components/LearnerWelcomeBanner'
import { Badge } from '../components/ui/Badge'
import type { BadgeVariant } from '../components/ui/Badge'
import { Banner } from '../components/ui/Banner'
import { Card } from '../components/ui/Card'
import { ProgressBar } from '../components/ProgressBar'
import { useAuth } from '../context/AuthContext'
import { fetchAssignments, fetchMySubmissions } from '../lib/assignmentsApi'
import { fetchCertificates } from '../lib/certificatesApi'
import { fetchCourseDetail, fetchCourses, fetchEnrollments } from '../lib/coursesApi'
import { fetchLeaderboard, fetchMyBadges } from '../lib/gamificationApi'
import { fetchMyAssessmentLevel } from '../lib/levelAssessmentsApi'
import { fetchQuizzes } from '../lib/quizApi'
import { isAdminRole } from '../lib/roles'
import type { Certificate } from '../types/certificates'
import type { User } from '../types/auth'
import type { Assignment } from '../types/assignment'
import type { CourseListItem, Enrollment } from '../types/courses'
import type { LeaderboardEntry, UserBadge } from '../types/gamification'
import type { MyAssessmentLevelStatus } from '../types/levelAssessments'
import type { QuizListItem } from '../types/quiz'

function isThisMonth(isoDate: string): boolean {
  const date = new Date(isoDate)
  const now = new Date()
  return date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth()
}

function StatCard({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: number }) {
  return (
    <Card className="flex items-center gap-4">
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-brand-navy/10 text-brand-navy">
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-2xl font-semibold text-neutral-900">{value}</p>
        <p className="text-xs text-neutral-500">{label}</p>
      </div>
    </Card>
  )
}

export function DashboardPage() {
  const { user } = useAuth()
  const [showWelcome, setShowWelcome] = useState(true)
  const isAdmin = isAdminRole(user?.role)

  return (
    <div className="space-y-6">
      {isAdmin && showWelcome && (
        <Banner
          variant="info"
          title={`Welcome back${user?.first_name ? `, ${user.first_name}` : ''}`}
          onDismiss={() => setShowWelcome(false)}
        />
      )}

      {isAdmin ? <AdminDashboard /> : user && <LearnerDashboard user={user} />}
    </div>
  )
}

function AdminDashboard() {
  const [courses, setCourses] = useState<CourseListItem[] | null>(null)
  const [enrollments, setEnrollments] = useState<Enrollment[] | null>(null)
  const [quizzes, setQuizzes] = useState<QuizListItem[] | null>(null)
  const [certificates, setCertificates] = useState<Certificate[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    Promise.all([fetchCourses(), fetchEnrollments(), fetchQuizzes(), fetchCertificates()])
      .then(([courseList, enrollmentList, quizList, certificateList]) => {
        if (cancelled) return
        setCourses(courseList)
        setEnrollments(enrollmentList)
        setQuizzes(quizList)
        setCertificates(certificateList)
      })
      .catch(() => {
        if (!cancelled) setError('Some dashboard data could not be loaded.')
      })

    return () => {
      cancelled = true
    }
  }, [])

  const recentCourses = courses
    ? [...courses].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()).slice(0, 3)
    : []

  // Quiz has no timestamp of its own — id ordering (most recently created
  // last) stands in as a "recent activity" proxy.
  const recentQuizzes = quizzes ? [...quizzes].sort((a, b) => b.id - a.id).slice(0, 3) : []

  const activeLearnerCount = enrollments
    ? new Set(enrollments.filter((enrollment) => enrollment.status !== 'NOT_STARTED').map((enrollment) => enrollment.user))
        .size
    : 0

  const certificatesThisMonth = certificates
    ? certificates.filter((certificate) => isThisMonth(certificate.issued_at)).length
    : 0

  const publishedCourseCount = courses ? courses.filter((course) => course.is_published).length : 0

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard icon={Users} label="Active Learners" value={activeLearnerCount} />
        <StatCard icon={Award} label="Certificates Issued This Month" value={certificatesThisMonth} />
        <StatCard icon={BookOpen} label="Published Courses" value={publishedCourseCount} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-neutral-900">Courses</h2>
            <Link to="/admin/courses" className="text-xs font-medium text-brand-navy hover:underline">
              View all Courses
            </Link>
          </div>

          {!courses ? (
            <p className="mt-4 text-sm text-neutral-500">Loading…</p>
          ) : recentCourses.length === 0 ? (
            <p className="mt-4 text-sm text-neutral-500">No courses yet.</p>
          ) : (
            <ul className="mt-4 space-y-3">
              {recentCourses.map((course) => (
                <li key={course.id} className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-neutral-900">{course.title}</p>
                    <p className="text-xs text-neutral-500">Updated {new Date(course.updated_at).toLocaleDateString()}</p>
                  </div>
                  <Badge variant={course.is_published ? 'navy' : 'neutral'}>
                    {course.is_published ? 'Published' : 'Draft'}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-neutral-900">Assessments</h2>
            <Link to="/assessments" className="text-xs font-medium text-brand-navy hover:underline">
              View all Assessments
            </Link>
          </div>

          {!quizzes ? (
            <p className="mt-4 text-sm text-neutral-500">Loading…</p>
          ) : recentQuizzes.length === 0 ? (
            <div className="mt-4 flex flex-col items-center gap-3 py-6 text-center">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-navy/10 text-brand-navy">
                <ClipboardList className="h-5 w-5" />
              </div>
              <p className="text-sm text-neutral-500">No quiz activity yet.</p>
              <Link
                to="/admin/courses"
                className="inline-flex items-center rounded-md bg-brand-navy px-3 py-1.5 text-xs font-medium text-white transition hover:bg-brand-navy-light"
              >
                Create your first Exam
              </Link>
            </div>
          ) : (
            <ul className="mt-4 space-y-3">
              {recentQuizzes.map((quiz) => (
                <li key={quiz.id} className="flex items-center justify-between gap-3">
                  <p className="truncate text-sm font-medium text-neutral-900">{quiz.title}</p>
                  <Badge variant="navy">
                    {quiz.questions.length} question{quiz.questions.length === 1 ? '' : 's'}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}

const STATUS_LABEL: Record<string, string> = {
  NOT_STARTED: 'Not started',
  IN_PROGRESS: 'In progress',
  COMPLETED: 'Completed',
}

const STATUS_BADGE: Record<string, BadgeVariant> = {
  NOT_STARTED: 'neutral',
  IN_PROGRESS: 'navy',
  COMPLETED: 'gold',
}

const LEVEL_ASSESSMENT_STATUS_LABEL: Record<string, string> = {
  NOT_STARTED: 'Not started',
  IN_PROGRESS: 'In progress',
  PASSED: 'Passed',
  FAILED: 'Failed — retake available',
}

const LEVEL_ASSESSMENT_STATUS_CLASSES: Record<string, string> = {
  NOT_STARTED: 'bg-neutral-100 text-neutral-700',
  IN_PROGRESS: 'bg-brand-navy/10 text-brand-navy',
  PASSED: 'bg-emerald-100 text-emerald-800',
  FAILED: 'bg-red-100 text-red-700',
}

function LevelAssessmentCard({ myLevelAssessment }: { myLevelAssessment: MyAssessmentLevelStatus | null }) {
  if (myLevelAssessment !== null && !myLevelAssessment.assigned) return null

  return (
    <Card>
      <h2 className="text-sm font-semibold text-neutral-900">My Level Assessment</h2>

      {!myLevelAssessment ? (
        <p className="mt-4 text-sm text-neutral-500">Loading…</p>
      ) : (
        <Link
          to="/level-assessment"
          className="mt-4 flex items-center justify-between gap-3 rounded-md border border-neutral-200 p-3 hover:bg-neutral-50"
        >
          <p className="text-sm font-medium text-neutral-900">{myLevelAssessment.assessment_level?.name_display}</p>
          <span
            className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${
              LEVEL_ASSESSMENT_STATUS_CLASSES[myLevelAssessment.status ?? 'NOT_STARTED']
            }`}
          >
            {LEVEL_ASSESSMENT_STATUS_LABEL[myLevelAssessment.status ?? 'NOT_STARTED']}
          </span>
        </Link>
      )}
    </Card>
  )
}

interface PendingAssignment {
  assignment: Assignment
  slideTitle: string
  courseTitle: string
  courseSlug: string
}

function LearnerDashboard({ user }: { user: User }) {
  const [enrollments, setEnrollments] = useState<Enrollment[] | null>(null)
  const [courses, setCourses] = useState<CourseListItem[]>([])
  const [pendingAssignments, setPendingAssignments] = useState<PendingAssignment[] | null>(null)
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[] | null>(null)
  const [myBadges, setMyBadges] = useState<UserBadge[] | null>(null)
  const [myLevelAssessment, setMyLevelAssessment] = useState<MyAssessmentLevelStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    Promise.all([fetchLeaderboard(), fetchMyBadges(), fetchMyAssessmentLevel()])
      .then(([entries, badges, levelAssessment]) => {
        if (cancelled) return
        setLeaderboard(entries)
        setMyBadges(badges)
        setMyLevelAssessment(levelAssessment)
      })
      .catch(() => {
        if (!cancelled) setError('Some dashboard data could not be loaded.')
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [enrollmentList, courseList] = await Promise.all([fetchEnrollments(), fetchCourses()])
        if (cancelled) return
        setEnrollments(enrollmentList)
        setCourses(courseList)

        const courseById = new Map(courseList.map((course) => [course.id, course]))
        const enrolledCourses = enrollmentList
          .map((enrollment) => courseById.get(enrollment.course))
          .filter((course): course is CourseListItem => !!course)

        const details = await Promise.all(enrolledCourses.map((course) => fetchCourseDetail(course.slug).catch(() => null)))
        if (cancelled) return

        // Slide id -> which enrolled course/slide it belongs to, so a flat
        // assignment list (which only knows its slide id) can be matched back
        // to "my enrolled courses" and labeled meaningfully.
        const assignmentSlideMeta = new Map<number, { slideTitle: string; courseTitle: string; courseSlug: string }>()
        for (const detail of details) {
          if (!detail) continue
          for (const courseModule of detail.modules) {
            for (const lesson of courseModule.lessons) {
              for (const slide of lesson.slides) {
                if (slide.slide_type === 'ASSIGNMENT') {
                  assignmentSlideMeta.set(slide.id, {
                    slideTitle: slide.title || `Slide ${slide.order}`,
                    courseTitle: detail.title,
                    courseSlug: detail.slug,
                  })
                }
              }
            }
          }
        }

        if (assignmentSlideMeta.size === 0) {
          if (!cancelled) setPendingAssignments([])
          return
        }

        const allAssignments = await fetchAssignments()
        if (cancelled) return
        const myAssignments = allAssignments.filter((assignment) => assignmentSlideMeta.has(assignment.slide))

        const withStatus = await Promise.all(
          myAssignments.map(async (assignment) => {
            const submissions = await fetchMySubmissions(assignment.id)
            return { assignment, hasSubmission: submissions.length > 0 }
          }),
        )
        if (cancelled) return

        setPendingAssignments(
          withStatus
            .filter((item) => !item.hasSubmission)
            .map((item) => ({ assignment: item.assignment, ...assignmentSlideMeta.get(item.assignment.slide)! })),
        )
      } catch {
        if (!cancelled) setError('Some dashboard data could not be loaded.')
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  const courseById = new Map(courses.map((course) => [course.id, course]))

  const myPoints = leaderboard?.find((entry) => entry.user_id === user.id)?.total_points ?? 0

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-red-600">{error}</p>}

      <LearnerWelcomeBanner
        user={user}
        totalCourses={enrollments?.length ?? null}
        completedCourses={enrollments ? enrollments.filter((enrollment) => enrollment.status === 'COMPLETED').length : null}
        points={leaderboard ? myPoints : null}
        badgesEarned={myBadges?.length ?? null}
      />

      <LeaderboardWidget entries={leaderboard} />

      <LevelAssessmentCard myLevelAssessment={myLevelAssessment} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-neutral-900">My Courses</h2>
            <Link to="/courses" className="text-xs font-medium text-brand-navy hover:underline">
              View all Courses
            </Link>
          </div>

          {!enrollments ? (
            <p className="mt-4 text-sm text-neutral-500">Loading…</p>
          ) : enrollments.length === 0 ? (
            <p className="mt-4 text-sm text-neutral-500">
              You're not enrolled in any courses yet — visit Courses to get started.
            </p>
          ) : (
            <ul className="mt-4 space-y-4">
              {enrollments.map((enrollment) => {
                const course = courseById.get(enrollment.course)
                const deadline =
                  course?.completion_deadline_days != null
                    ? new Date(
                        new Date(enrollment.enrolled_at).getTime() + course.completion_deadline_days * 24 * 60 * 60 * 1000,
                      )
                    : null
                const isOverdue = deadline !== null && deadline.getTime() < Date.now() && enrollment.status !== 'COMPLETED'

                return (
                  <li key={enrollment.id}>
                    <div className="flex items-center justify-between gap-3">
                      <p className="truncate text-sm font-medium text-neutral-900">
                        {course?.title ?? `Course #${enrollment.course}`}
                      </p>
                      <Badge variant={STATUS_BADGE[enrollment.status] ?? 'neutral'}>
                        {STATUS_LABEL[enrollment.status] ?? enrollment.status}
                      </Badge>
                    </div>
                    <div className="mt-1.5">
                      <ProgressBar percent={enrollment.progress_percent} />
                    </div>
                    {deadline && (
                      <p className={`mt-1 flex items-center gap-1 text-xs ${isOverdue ? 'text-red-600' : 'text-neutral-400'}`}>
                        <CalendarClock className="h-3 w-3" />
                        {isOverdue ? 'Overdue — was due' : 'Due'} {deadline.toLocaleDateString()}
                      </p>
                    )}
                    {enrollment.status === 'COMPLETED' && enrollment.certificate_ineligible_reason && course && (
                      <div className="mt-1.5">
                        <p className="text-xs text-amber-700">{enrollment.certificate_ineligible_reason}</p>
                        <Link
                          to={`/courses/${course.slug}`}
                          className="text-xs font-medium text-brand-navy hover:underline"
                        >
                          Retake Course
                        </Link>
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </Card>

        <Card>
          <h2 className="text-sm font-semibold text-neutral-900">Pending Assignments</h2>

          {!pendingAssignments ? (
            <p className="mt-4 text-sm text-neutral-500">Loading…</p>
          ) : pendingAssignments.length === 0 ? (
            <div className="mt-4 flex flex-col items-center gap-2 py-6 text-center">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-navy/10 text-brand-navy">
                <ClipboardList className="h-5 w-5" />
              </div>
              <p className="text-sm text-neutral-500">Nothing pending — you're all caught up.</p>
            </div>
          ) : (
            <ul className="mt-4 space-y-3">
              {pendingAssignments.map(({ assignment, slideTitle, courseTitle, courseSlug }) => (
                <li key={assignment.id}>
                  <Link to={`/courses/${courseSlug}`} className="block rounded-md border border-neutral-200 p-3 hover:bg-neutral-50">
                    <p className="text-sm font-medium text-neutral-900">{slideTitle}</p>
                    <p className="text-xs text-neutral-500">{courseTitle}</p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <BadgesWidget badges={myBadges} />
    </div>
  )
}
