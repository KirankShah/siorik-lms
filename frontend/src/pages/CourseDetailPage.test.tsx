import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CourseDetailPage } from './CourseDetailPage'
import * as coursesApi from '../lib/coursesApi'
import type { CourseDetail, Enrollment } from '../types/courses'
import type { User } from '../types/auth'

vi.mock('../lib/coursesApi')

// SlidePlayer's own gating logic is covered by SlidePlayer.test.tsx — this
// stub only needs to surface the props CourseDetailPage computes for it, so
// these tests stay focused on CourseDetailPage's own preview-mode wiring
// (enrollment requirement, reachedSlideIds, the banner) rather than
// re-testing SlidePlayer's internals.
vi.mock('../components/player/SlidePlayer', () => ({
  SlidePlayer: ({ slide, enrollmentId, previewMode }: { slide: { title: string }; enrollmentId: number | null; previewMode?: boolean }) => (
    <div data-testid="slide-player" data-preview={String(!!previewMode)} data-enrollment-id={String(enrollmentId)}>
      {slide.title}
    </div>
  ),
}))

let mockUser: User | null = null
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}))

function makeUser(role: User['role']): User {
  return {
    id: 1,
    email: 'user@example.com',
    first_name: 'Test',
    last_name: 'User',
    role,
    organization: { id: 1, name: 'Acme', slug: 'acme', logo: null, is_active: true },
    phone_number: null,
    designation: null,
    corporate_title: null,
    functional_title: null,
    branch_department: null,
    assessment_level: null,
    is_active: true,
    is_demo: false,
    must_reset_password: false,
    preferred_narration_language: 'en',
  }
}

function makeCourse(): CourseDetail {
  return {
    id: 1,
    title: 'Test Course',
    slug: 'test-course',
    description: '',
    organization: 1,
    organization_name: 'Acme',
    content_owner: 'ORGANIZATION',
    cover_image: null,
    is_published: true,
    template: null,
    completion_deadline_days: null,
    path_order: null,
    minimum_assessment_level: null,
    cloned_from_title: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    is_locked: false,
    path_state: null,
    created_by: null,
    certificate_expiry_months: null,
    is_demo_available: false,
    access_grants: [],
    modules: [
      {
        id: 1,
        title: 'Module 1',
        order: 1,
        lessons: [
          {
            id: 1,
            title: 'Lesson 1',
            lesson_type: 'SLIDES',
            content_file: null,
            content_url: '',
            order: 1,
            estimated_minutes: 5,
            is_locked: false,
            slides: [
              {
                id: 1,
                title: 'Slide One',
                order: 1,
                slide_type: 'CONTENT',
                layout: 'STACKED',
                image_column_width: 'STANDARD',
                template_override: null,
                estimated_minutes: 5,
              },
              {
                id: 2,
                title: 'Slide Two',
                order: 2,
                slide_type: 'CONTENT',
                layout: 'STACKED',
                image_column_width: 'STANDARD',
                template_override: null,
                estimated_minutes: 5,
              },
              {
                id: 3,
                title: 'Slide Three',
                order: 3,
                slide_type: 'CONTENT',
                layout: 'STACKED',
                image_column_width: 'STANDARD',
                template_override: null,
                estimated_minutes: 5,
              },
            ],
          },
        ],
      },
    ],
  }
}

function makeEnrollment(overrides: Partial<Enrollment> = {}): Enrollment {
  return {
    id: 1,
    user: 1,
    course: 1,
    course_title: 'Test Course',
    course_slug: 'test-course',
    course_completion_deadline_days: null,
    enrolled_at: '2026-01-01T00:00:00Z',
    completed_at: null,
    status: 'IN_PROGRESS',
    progress_percent: 0,
    completed_lesson_ids: [],
    slide_progress: [],
    certificate_ineligible_reason: null,
    retake_count: 0,
    retake_limit_reached: false,
    ...overrides,
  }
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/courses/:id" element={<CourseDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('CourseDetailPage admin preview mode', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(coursesApi.fetchCourseDetail).mockResolvedValue(makeCourse())
  })

  it('lets an ORG_ADMIN with ?preview=1 reach every slide without ever enrolling', async () => {
    mockUser = makeUser('ORG_ADMIN')

    renderAt('/courses/test-course?preview=1')

    expect(await screen.findByText('Preview Mode — no progress is being recorded, and every slide is unlocked for review.')).toBeInTheDocument()

    // Every slide is reachable, including the last one — the sidebar never
    // disables anything ahead of the current slide (there is no enrollment
    // at all to derive a frontier from).
    const slideOneButton = await screen.findByRole('button', { name: /Slide One/ })
    const slideTwoButton = await screen.findByRole('button', { name: /Slide Two/ })
    const slideThreeButton = await screen.findByRole('button', { name: /Slide Three/ })
    expect(slideOneButton).toBeEnabled()
    expect(slideTwoButton).toBeEnabled()
    expect(slideThreeButton).toBeEnabled()

    // The stubbed SlidePlayer received previewMode=true and no real enrollment id.
    const player = await screen.findByTestId('slide-player')
    expect(player).toHaveAttribute('data-preview', 'true')
    expect(player).toHaveAttribute('data-enrollment-id', 'null')

    expect(coursesApi.fetchEnrollments).not.toHaveBeenCalled()
    expect(coursesApi.enrollInCourse).not.toHaveBeenCalled()
  })

  it('ignores ?preview=1 for a LEARNER and leaves the sequential slide lock fully intact', async () => {
    mockUser = makeUser('LEARNER')
    vi.mocked(coursesApi.fetchEnrollments).mockResolvedValue([
      makeEnrollment({
        slide_progress: [
          { id: 1, slide: 1, time_spent_seconds: 300, completed_at: '2026-01-01T00:05:00Z', started_at: '2026-01-01T00:00:00Z' },
        ],
      }),
    ])

    renderAt('/courses/test-course?preview=1')

    // No preview banner, and Slide Three — beyond the reached frontier
    // (Slide One completed, Slide Two is the current/next slide) — stays
    // locked even though the URL carries the same ?preview=1 an admin would use.
    expect(
      screen.queryByText('Preview Mode — no progress is being recorded, and every slide is unlocked for review.'),
    ).not.toBeInTheDocument()

    const slideThreeButton = await screen.findByRole('button', { name: /Slide Three/ })
    expect(slideThreeButton).toBeDisabled()

    const player = await screen.findByTestId('slide-player')
    expect(player).toHaveAttribute('data-preview', 'false')

    await waitFor(() => expect(coursesApi.fetchEnrollments).toHaveBeenCalled())
  })
})
