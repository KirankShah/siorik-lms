import { useEffect, useMemo, useState } from 'react'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { ApiError } from '../../lib/apiClient'
import { fetchAssessmentLevels, importLevelQuestions, updateAssessmentLevel } from '../../lib/levelAssessmentsApi'
import type { AssessmentLevelSummary, LevelQuestionImportResult } from '../../types/levelAssessments'

const TEMPLATE_COLUMNS = [
  'Question Set',
  'Question Text',
  'Question Type',
  'Option A',
  'Option B',
  'Option C',
  'Option D',
  'Option E',
  'Correct Answer(s)',
  'Marks',
  'Explanation',
  'Feedback if Correct',
  'Feedback if Incorrect',
]

function LevelSettingsCard({
  level,
  onSaved,
}: {
  level: AssessmentLevelSummary
  onSaved: (updated: AssessmentLevelSummary) => void
}) {
  const [passThreshold, setPassThreshold] = useState(String(level.pass_threshold))
  const [questionsPerAttempt, setQuestionsPerAttempt] = useState(String(level.questions_per_attempt))
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

  // Re-sync when the selected level changes.
  useEffect(() => {
    setPassThreshold(String(level.pass_threshold))
    setQuestionsPerAttempt(String(level.questions_per_attempt))
    setStatus('idle')
  }, [level.id, level.pass_threshold, level.questions_per_attempt])

  const pass = Number(passThreshold)
  const perAttempt = Number(questionsPerAttempt)
  const valid =
    Number.isInteger(pass) && pass >= 0 && pass <= 100 && Number.isInteger(perAttempt) && perAttempt >= 1
  const dirty = pass !== level.pass_threshold || perAttempt !== level.questions_per_attempt

  async function save() {
    if (!valid || !dirty) return
    setStatus('saving')
    try {
      const updated = await updateAssessmentLevel(level.id, {
        pass_threshold: pass,
        questions_per_attempt: perAttempt,
      })
      onSaved(updated)
      setStatus('saved')
    } catch {
      setStatus('error')
    }
  }

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-neutral-900">Level settings — {level.name_display}</h2>
        <p className="mt-1 text-sm text-neutral-500">
          Each organization sets its own pass mark. An attempt draws the number of questions below at random from this
          level's pool, so the pool must hold at least that many questions before a learner can start.
        </p>
      </div>
      <div className="flex flex-wrap gap-4">
        <label className="text-sm">
          <span className="block font-medium text-neutral-700">Pass mark (%)</span>
          <input
            type="number"
            min={0}
            max={100}
            value={passThreshold}
            onChange={(e) => setPassThreshold(e.target.value)}
            className="mt-1 w-28 rounded-md border border-neutral-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm">
          <span className="block font-medium text-neutral-700">Questions per attempt</span>
          <input
            type="number"
            min={1}
            value={questionsPerAttempt}
            onChange={(e) => setQuestionsPerAttempt(e.target.value)}
            className="mt-1 w-28 rounded-md border border-neutral-300 px-3 py-2 text-sm"
          />
        </label>
      </div>
      {!valid && (
        <p className="text-sm text-red-600">Pass mark must be 0–100 and questions per attempt at least 1.</p>
      )}
      {status === 'error' && <p className="text-sm text-red-600">Could not save the level settings.</p>}
      {status === 'saved' && !dirty && <p className="text-sm text-emerald-700">Level settings saved.</p>}
      <Button disabled={!valid || !dirty || status === 'saving'} onClick={save}>
        {status === 'saving' ? 'Saving…' : 'Save settings'}
      </Button>
    </Card>
  )
}

export function LevelQuestionsImportPage() {
  const [levels, setLevels] = useState<AssessmentLevelSummary[]>([])
  const [levelsError, setLevelsError] = useState<string | null>(null)
  const [levelId, setLevelId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<LevelQuestionImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    fetchAssessmentLevels()
      .then(setLevels)
      .catch(() => setLevelsError('Could not load assessment levels.'))
  }, [])

  // A PLATFORM_ADMIN sees several organizations' levels at once, so the label
  // needs the org name to stay unambiguous; an ORG_ADMIN sees only their own.
  const showOrg = useMemo(() => new Set(levels.map((level) => level.organization.id)).size > 1, [levels])
  const selectedLevel = levels.find((level) => String(level.id) === levelId) ?? null

  function applyLevelUpdate(updated: AssessmentLevelSummary) {
    setLevels((prev) => prev.map((level) => (level.id === updated.id ? updated : level)))
  }

  async function handleSubmit() {
    if (!levelId || !file) return
    setIsSubmitting(true)
    setError(null)
    setResult(null)
    try {
      setResult(await importLevelQuestions(Number(levelId), file))
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const body = err.body as { detail?: string } | null
        setError(body?.detail ?? 'The file could not be read as an .xlsx workbook.')
      } else {
        setError('Could not import the questions. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Level Assessments</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Configure each role-based assessment level's pass mark and import its questions. Staff are shown the assessment
        for the level they were enrolled at — no per-person assignment step.
      </p>

      <Card className="mt-4 space-y-4">
        <div>
          <label htmlFor="import-level" className="block text-sm font-medium text-neutral-700">
            Assessment level
          </label>
          <select
            id="import-level"
            value={levelId}
            onChange={(e) => {
              setLevelId(e.target.value)
              setResult(null)
              setError(null)
            }}
            className="mt-1 w-full max-w-sm rounded-md border border-neutral-300 px-3 py-2 text-sm"
          >
            <option value="">Select a level…</option>
            {levels.map((level) => (
              <option key={level.id} value={level.id}>
                {showOrg ? `${level.organization.name} — ${level.name_display}` : level.name_display}
              </option>
            ))}
          </select>
          {levelsError && <p className="mt-1 text-sm text-red-600">{levelsError}</p>}
          {!levelsError && levels.length === 0 && (
            <p className="mt-1 text-sm text-neutral-500">No assessment levels found for your organization.</p>
          )}
        </div>
      </Card>

      {selectedLevel && (
        <div className="mt-4">
          <LevelSettingsCard level={selectedLevel} onSaved={applyLevelUpdate} />
        </div>
      )}

      <Card className="mt-4 space-y-4">
        <div>
          <h2 className="text-sm font-semibold text-neutral-900">Import questions</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Bulk-import questions from a "Level Assessment Question Template" Excel workbook into the selected level.
            Each valid row is committed immediately; invalid rows are skipped and listed below with a reason — they
            never block the rest of the file.
          </p>
        </div>

        <div>
          <label htmlFor="import-file" className="block text-sm font-medium text-neutral-700">
            Excel file (.xlsx)
          </label>
          <input
            id="import-file"
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-1 text-sm"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Button disabled={!levelId || !file || isSubmitting} onClick={handleSubmit}>
          {isSubmitting ? 'Importing…' : 'Import Questions'}
        </Button>
      </Card>

      <Card className="mt-4">
        <h2 className="text-sm font-semibold text-neutral-900">Template format</h2>
        <p className="mt-1 text-sm text-neutral-500">
          Every worksheet in the workbook is processed. The first row of each sheet must be a header row containing all
          of these columns (any order, case-insensitive):
        </p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {TEMPLATE_COLUMNS.map((column) => (
            <code key={column} className="rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-700">
              {column}
            </code>
          ))}
        </div>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-neutral-500">
          <li>
            <span className="font-medium text-neutral-700">Question Set</span> groups questions into a named set (e.g.
            "Set 1"); it is created automatically under the chosen level if it doesn't exist.
          </li>
          <li>
            <span className="font-medium text-neutral-700">Question Type</span> must be{' '}
            <code className="rounded bg-neutral-100 px-1 py-0.5 text-xs">Single Choice</code> or{' '}
            <code className="rounded bg-neutral-100 px-1 py-0.5 text-xs">Multiple Answer</code>.
          </li>
          <li>
            <span className="font-medium text-neutral-700">Option A–D</span> are required; Option E is optional.
          </li>
          <li>
            <span className="font-medium text-neutral-700">Correct Answer(s)</span> is a comma-separated list of option
            letters (e.g. <code className="rounded bg-neutral-100 px-1 py-0.5 text-xs">A</code> or{' '}
            <code className="rounded bg-neutral-100 px-1 py-0.5 text-xs">A, C</code>) — exactly one for Single Choice.
          </li>
          <li>
            <span className="font-medium text-neutral-700">Marks</span> must be a positive whole number. Explanation and
            both Feedback columns are optional.
          </li>
        </ul>
      </Card>

      {result && (
        <Card className="mt-4 space-y-3">
          <p className="text-sm text-emerald-700">
            Imported {result.created.length} question{result.created.length === 1 ? '' : 's'}.
          </p>

          {result.failed.length > 0 ? (
            <div>
              <p className="text-sm font-medium text-red-700">
                {result.failed.length} row{result.failed.length === 1 ? '' : 's'} skipped:
              </p>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-neutral-500 uppercase">
                    <tr>
                      <th className="py-1 pr-3">Sheet</th>
                      <th className="py-1 pr-3">Row</th>
                      <th className="py-1">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.failed.map((failure, index) => (
                      <tr key={`${failure.sheet}-${failure.row}-${index}`} className="border-t border-neutral-100">
                        <td className="py-1 pr-3 text-neutral-900">{failure.sheet}</td>
                        <td className="py-1 pr-3 text-neutral-500">{failure.row ?? 'header'}</td>
                        <td className="py-1 text-neutral-600">{failure.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            result.created.length > 0 && <p className="text-sm text-neutral-500">Every row imported cleanly.</p>
          )}
        </Card>
      )}
    </div>
  )
}
