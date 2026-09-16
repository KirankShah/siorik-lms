import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowDown, ArrowUp } from 'lucide-react'
import { Card } from '../../components/ui/Card'
import { useAuth } from '../../context/AuthContext'
import { fetchOrganizations } from '../../lib/accountsApi'
import {
  assignCourseToLevel,
  fetchLevelCourseAssignments,
  reorderLevelCourseAssignments,
  unassignCourseFromLevel,
} from '../../lib/coursesApi'
import { fetchAssessmentLevels } from '../../lib/levelAssessmentsApi'
import { isPlatformAdminRole } from '../../lib/roles'
import type { Organization } from '../../types/auth'
import type { AssignableCourse, LevelCourseAssignment } from '../../types/courses'
import type { AssessmentLevelSummary } from '../../types/levelAssessments'

export function RoleBasedTrainingPage() {
  const { user } = useAuth()
  const isPlatformAdmin = isPlatformAdminRole(user?.role)

  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [orgFilter, setOrgFilter] = useState('')

  const [levels, setLevels] = useState<AssessmentLevelSummary[]>([])
  const [levelsError, setLevelsError] = useState<string | null>(null)
  const [selectedLevelId, setSelectedLevelId] = useState<number | null>(null)

  const [assigned, setAssigned] = useState<LevelCourseAssignment[]>([])
  const [unassigned, setUnassigned] = useState<AssignableCourse[]>([])
  const [listError, setListError] = useState<string | null>(null)
  const [isLoadingList, setIsLoadingList] = useState(false)
  const [busy, setBusy] = useState(false)
  const selectedLevelRef = useRef<number | null>(null)
  const assignmentRequestId = useRef(0)
  selectedLevelRef.current = selectedLevelId

  useEffect(() => {
    if (isPlatformAdmin) fetchOrganizations().then(setOrganizations).catch(() => {})
  }, [isPlatformAdmin])

  useEffect(() => {
    fetchAssessmentLevels()
      .then(setLevels)
      .catch(() => setLevelsError('Could not load assessment levels.'))
  }, [])

  const visibleLevels = useMemo(() => {
    if (!isPlatformAdmin) return levels
    if (!orgFilter) return []
    return levels.filter((level) => level.organization.id === Number(orgFilter))
  }, [levels, isPlatformAdmin, orgFilter])

  // Default to the first visible level whenever the visible set changes
  // (org switched, or levels just loaded) — never leaves a stale selection
  // pointing at a level that's no longer shown.
  useEffect(() => {
    if (visibleLevels.length === 0) {
      setSelectedLevelId(null)
      return
    }
    if (!visibleLevels.some((level) => level.id === selectedLevelId)) {
      setSelectedLevelId(visibleLevels[0].id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleLevels])

  function loadAssignments(levelId: number | null) {
    const requestId = ++assignmentRequestId.current
    if (levelId === null) {
      setAssigned([])
      setUnassigned([])
      setListError(null)
      setIsLoadingList(false)
      return Promise.resolve()
    }
    setIsLoadingList(true)
    setListError(null)
    return fetchLevelCourseAssignments(levelId)
      .then((data) => {
        if (requestId !== assignmentRequestId.current || selectedLevelRef.current !== levelId) return
        setAssigned(data.assigned)
        setUnassigned(data.unassigned)
      })
      .catch(() => {
        if (requestId === assignmentRequestId.current && selectedLevelRef.current === levelId) {
          setListError('Could not load this level\'s course assignments.')
        }
      })
      .finally(() => {
        if (requestId === assignmentRequestId.current && selectedLevelRef.current === levelId) {
          setIsLoadingList(false)
        }
      })
  }

  useEffect(() => {
    void loadAssignments(selectedLevelId)
  }, [selectedLevelId]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleAssign(course: AssignableCourse) {
    if (selectedLevelId === null || busy) return
    setBusy(true)
    try {
      await assignCourseToLevel(selectedLevelId, course.id)
      if (selectedLevelRef.current === selectedLevelId) await loadAssignments(selectedLevelId)
    } catch {
      setListError('Could not assign this course. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  async function handleUnassign(assignment: LevelCourseAssignment) {
    if (busy) return
    setBusy(true)
    try {
      await unassignCourseFromLevel(assignment.id)
      if (selectedLevelRef.current === selectedLevelId) await loadAssignments(selectedLevelId)
    } catch {
      setListError('Could not unassign this course. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  async function handleMove(index: number, direction: -1 | 1) {
    if (selectedLevelId === null || busy) return
    const targetIndex = index + direction
    if (targetIndex < 0 || targetIndex >= assigned.length) return

    const reordered = [...assigned]
    const [moved] = reordered.splice(index, 1)
    reordered.splice(targetIndex, 0, moved)

    setBusy(true)
    try {
      const result = await reorderLevelCourseAssignments(
        selectedLevelId,
        reordered.map((a) => a.course_id),
      )
      setAssigned(result)
    } catch {
      setListError('Could not save the new order. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const selectedLevel = visibleLevels.find((level) => level.id === selectedLevelId) ?? null

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-neutral-900">Role-Based Training</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Configure course assignments and ordering for each assessment level. These settings do not yet change live
          learner paths.
        </p>
      </div>

      {isPlatformAdmin && (
        <Card>
          <label className="block text-xs font-medium text-neutral-500">Organization</label>
          <select
            value={orgFilter}
            onChange={(e) => setOrgFilter(e.target.value)}
            className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
          >
            <option value="">Select an organization…</option>
            {organizations.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </select>
        </Card>
      )}

      {levelsError && <p className="text-sm text-red-600">{levelsError}</p>}

      {(!isPlatformAdmin || orgFilter) && (
        <Card>
          <div className="flex flex-wrap gap-2">
            {visibleLevels.map((level) => (
              <button
                key={level.id}
                type="button"
                onClick={() => setSelectedLevelId(level.id)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  level.id === selectedLevelId
                    ? 'bg-brand-navy text-white'
                    : 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200'
                }`}
              >
                {level.name_display}
              </button>
            ))}
            {visibleLevels.length === 0 && (
              <p className="text-sm text-neutral-400">No assessment levels found for this organization.</p>
            )}
          </div>
        </Card>
      )}

      {selectedLevel && (
        <Card>
          <h2 className="text-sm font-semibold text-neutral-900">{selectedLevel.name_display}</h2>

          {listError && <p className="mt-2 text-sm text-red-600">{listError}</p>}

          {isLoadingList ? (
            <p className="mt-4 text-sm text-neutral-500">Loading…</p>
          ) : (
            <div className="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2">
              <div>
                <h3 className="text-xs font-semibold tracking-wide text-neutral-500 uppercase">Unassigned Courses</h3>
                <ul className="mt-2 space-y-1">
                  {unassigned.map((course) => (
                    <li
                      key={course.id}
                      className="flex items-center justify-between gap-2 rounded-md border border-neutral-200 px-3 py-2 text-sm"
                    >
                      <span className="min-w-0 flex-1 truncate text-neutral-800">{course.title}</span>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void handleAssign(course)}
                        className="shrink-0 text-xs font-medium text-brand-navy underline disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        Assign →
                      </button>
                    </li>
                  ))}
                  {unassigned.length === 0 && (
                    <li className="rounded-md border border-dashed border-neutral-200 px-3 py-4 text-center text-sm text-neutral-400">
                      Nothing left to assign.
                    </li>
                  )}
                </ul>
              </div>

              <div>
                <h3 className="text-xs font-semibold tracking-wide text-neutral-500 uppercase">Assigned Courses</h3>
                <ul className="mt-2 space-y-1">
                  {assigned.map((assignment, index) => (
                    <li
                      key={assignment.id}
                      className="flex items-center justify-between gap-2 rounded-md border border-neutral-200 px-3 py-2 text-sm"
                    >
                      <span className="w-5 shrink-0 text-xs font-medium text-neutral-400">{index + 1}.</span>
                      <span className="min-w-0 flex-1 truncate text-neutral-800">{assignment.course_title}</span>
                      <div className="flex shrink-0 items-center gap-1">
                        <button
                          type="button"
                          disabled={busy || index === 0}
                          aria-label="Move up"
                          onClick={() => void handleMove(index, -1)}
                          className="rounded p-1 text-neutral-500 hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-30"
                        >
                          <ArrowUp className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          disabled={busy || index === assigned.length - 1}
                          aria-label="Move down"
                          onClick={() => void handleMove(index, 1)}
                          className="rounded p-1 text-neutral-500 hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-30"
                        >
                          <ArrowDown className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void handleUnassign(assignment)}
                          className="ml-1 text-xs font-medium text-red-600 underline disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          ← Unassign
                        </button>
                      </div>
                    </li>
                  ))}
                  {assigned.length === 0 && (
                    <li className="rounded-md border border-dashed border-neutral-200 px-3 py-4 text-center text-sm text-neutral-400">
                      No courses assigned to this level yet.
                    </li>
                  )}
                </ul>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
