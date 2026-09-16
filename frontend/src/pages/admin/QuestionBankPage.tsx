import { useEffect, useState } from 'react'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { DeleteQuestionModal } from '../../components/admin/DeleteQuestionModal'
import { QuestionEditModal } from '../../components/admin/QuestionEditModal'
import { useAuth } from '../../context/AuthContext'
import { fetchOrganizations } from '../../lib/accountsApi'
import type { PaginatedResult } from '../../lib/accountsApi'
import { fetchLevelQuestions } from '../../lib/levelAssessmentsApi'
import { isPlatformAdminRole } from '../../lib/roles'
import type { Organization } from '../../types/auth'
import type { LevelQuestionListItem } from '../../types/levelAssessments'

const ASSESSMENT_LEVELS: { value: string; label: string }[] = [
  { value: 'assistant_supervisor', label: 'Front-Line Level' },
  { value: 'officer', label: 'Officer Level' },
  { value: 'management', label: 'Middle Management Level' },
  { value: 'senior_management', label: 'Top Management Level' },
]

const PAGE_SIZE = 25
const TRUNCATE_LENGTH = 100

function truncate(text: string, length: number): string {
  return text.length > length ? `${text.slice(0, length)}…` : text
}

export function QuestionBankPage() {
  const { user } = useAuth()
  const isPlatformAdmin = isPlatformAdminRole(user?.role)

  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [orgFilter, setOrgFilter] = useState('')
  const [levelFilter, setLevelFilter] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)

  const [questionPage, setQuestionPage] = useState<PaginatedResult<LevelQuestionListItem> | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  // Platform admin starts with no organization chosen — rather than
  // auto-loading every organization's entire pool on mount, nothing is
  // fetched until they've touched at least one filter (organization, level,
  // or search). Non-platform-admins are always scoped to their own
  // organization server-side, so they can fetch immediately.
  const [hasInteracted, setHasInteracted] = useState(!isPlatformAdmin)

  const [viewingId, setViewingId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  useEffect(() => {
    if (isPlatformAdmin) fetchOrganizations().then(setOrganizations).catch(() => {})
  }, [isPlatformAdmin])

  useEffect(() => {
    const timeout = setTimeout(() => {
      setPage(1)
      setSearch(searchInput.trim())
      if (searchInput.trim()) setHasInteracted(true)
    }, 350)
    return () => clearTimeout(timeout)
  }, [searchInput])

  function loadQuestions() {
    if (!hasInteracted) return
    setListError(null)
    fetchLevelQuestions({
      organization: isPlatformAdmin && orgFilter ? Number(orgFilter) : undefined,
      assessment_level: levelFilter || undefined,
      search: search || undefined,
      page,
      page_size: PAGE_SIZE,
    })
      .then(setQuestionPage)
      .catch(() => setListError('Could not load the question bank.'))
  }

  useEffect(loadQuestions, [hasInteracted, orgFilter, levelFilter, search, page, isPlatformAdmin]) // eslint-disable-line react-hooks/exhaustive-deps

  const rows = questionPage?.results ?? []

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-neutral-900">Question Bank</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Browse, edit, and remove questions already imported into your organization's assessment levels.
        </p>
      </div>

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs font-medium text-neutral-500">Search</label>
            <input
              type="text"
              placeholder="Question text…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-neutral-500">Assessment Level</label>
            <select
              value={levelFilter}
              onChange={(e) => {
                setPage(1)
                setHasInteracted(true)
                setLevelFilter(e.target.value)
              }}
              className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
            >
              <option value="">All levels</option>
              {ASSESSMENT_LEVELS.map((level) => (
                <option key={level.value} value={level.value}>
                  {level.label}
                </option>
              ))}
            </select>
          </div>

          {isPlatformAdmin && (
            <div>
              <label className="block text-xs font-medium text-neutral-500">Organization</label>
              <select
                value={orgFilter}
                onChange={(e) => {
                  setPage(1)
                  setHasInteracted(true)
                  setOrgFilter(e.target.value)
                }}
                className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
              >
                <option value="">Select an organization…</option>
                {organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {listError && <p className="mt-4 text-sm text-red-600">{listError}</p>}

        {!hasInteracted ? (
          <p className="mt-6 text-center text-sm text-neutral-400">
            Select an organization, assessment level, or search term to view its question bank.
          </p>
        ) : (
          <>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-neutral-200 text-xs uppercase tracking-wide text-neutral-500">
                  <tr>
                    <th className="py-2 pr-3">Question Set</th>
                    <th className="py-2 pr-3">Question Text</th>
                    <th className="py-2 pr-3">Type</th>
                    <th className="py-2 pr-3">Correct Answer(s)</th>
                    <th className="py-2 pr-3">Marks</th>
                    <th className="py-2" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((question) => (
                    <tr key={question.id} className="border-b border-neutral-100 last:border-0 align-top">
                      <td className="py-2 pr-3 text-neutral-700">{question.question_set_label}</td>
                      <td className="py-2 pr-3 text-neutral-900" title={question.question_text}>
                        {truncate(question.question_text, TRUNCATE_LENGTH)}
                      </td>
                      <td className="py-2 pr-3 text-neutral-700">
                        {question.question_type === 'SINGLE_CHOICE' ? 'Single choice' : 'Multiple answer'}
                      </td>
                      <td className="py-2 pr-3 text-neutral-700">{question.correct_answers.join(', ') || '—'}</td>
                      <td className="py-2 pr-3 text-neutral-700">{question.marks}</td>
                      <td className="py-2 text-right whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => setViewingId(question.id)}
                          className="text-sm text-brand-navy underline"
                        >
                          View/Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeletingId(question.id)}
                          className="ml-3 text-sm text-red-600 underline"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                  {questionPage && rows.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-neutral-400">
                        No questions match these filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {questionPage && questionPage.count > 0 && (
              <div className="mt-4 flex items-center justify-between text-sm text-neutral-500">
                <span>{questionPage.count} total</span>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" disabled={!questionPage.previous} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </Button>
                  <Button variant="outline" size="sm" disabled={!questionPage.next} onClick={() => setPage((p) => p + 1)}>
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>

      {viewingId !== null && (
        <QuestionEditModal
          questionId={viewingId}
          onClose={() => setViewingId(null)}
          onSaved={() => {
            setViewingId(null)
            loadQuestions()
          }}
        />
      )}

      {deletingId !== null && (
        <DeleteQuestionModal
          questionId={deletingId}
          onClose={() => setDeletingId(null)}
          onDeleted={() => {
            setDeletingId(null)
            loadQuestions()
          }}
        />
      )}
    </div>
  )
}
