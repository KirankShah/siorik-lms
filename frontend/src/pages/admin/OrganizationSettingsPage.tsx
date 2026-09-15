import { useEffect, useState } from 'react'
import { Badge } from '../../components/ui/Badge'
import { Banner } from '../../components/ui/Banner'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { useAuth } from '../../context/AuthContext'
import { ApiError } from '../../lib/apiClient'
import { fetchOrganizationSettingsList, updateOrganizationSettings } from '../../lib/orgSettingsApi'
import { isPlatformAdminRole } from '../../lib/roles'
import type { OrganizationSettings, ReminderFrequency, TimingMode } from '../../types/orgSettings'

function extractFieldError(err: unknown): string | null {
  if (err instanceof ApiError && err.body && typeof err.body === 'object') {
    const value = Object.values(err.body as Record<string, unknown>)[0]
    if (typeof value === 'string') return value
    if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
  }
  return null
}

interface Draft {
  questions_per_attempt: string
  timing_mode: TimingMode
  seconds_per_question: string
  total_exam_minutes: string
  pass_mark_percent: string
}

function draftFromSettings(settings: OrganizationSettings): Draft {
  return {
    questions_per_attempt: String(settings.questions_per_attempt),
    timing_mode: settings.timing_mode,
    seconds_per_question: String(settings.seconds_per_question),
    total_exam_minutes: String(settings.total_exam_minutes),
    pass_mark_percent: String(settings.pass_mark_percent),
  }
}

// The three org-wide values that used to be scattered across the Course >
// Certification tab (certificate pass threshold) and the Level Assessment
// admin page (pass mark / questions per attempt, per level) — consolidated
// here so an admin edits them in exactly one place. Also governs the new
// per-question countdown timer on the sequential level-assessment flow.
function SettingsForm({
  settings,
  onSaved,
}: {
  settings: OrganizationSettings
  onSaved: (updated: OrganizationSettings) => void
}) {
  const [draft, setDraft] = useState<Draft>(draftFromSettings(settings))
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    setDraft(draftFromSettings(settings))
    setError(null)
    setSuccess(false)
  }, [settings])

  async function handleSave() {
    setIsSaving(true)
    setError(null)
    setSuccess(false)
    try {
      const updated = await updateOrganizationSettings(settings.id, {
        questions_per_attempt: Number(draft.questions_per_attempt),
        timing_mode: draft.timing_mode,
        seconds_per_question: Number(draft.seconds_per_question),
        total_exam_minutes: Number(draft.total_exam_minutes),
        pass_mark_percent: Number(draft.pass_mark_percent),
      })
      onSaved(updated)
      setSuccess(true)
    } catch (err) {
      setError(extractFieldError(err) ?? 'Could not save these settings.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Card className="mt-6 max-w-xl">
      <h2 className="text-sm font-semibold text-neutral-900">Assessment &amp; Certificate Settings</h2>
      <p className="mt-1 text-sm text-neutral-500">
        Applies to every Level Assessment tier and every course's certificate for this organization — one shared
        configuration instead of setting it separately per course or per assessment level.
      </p>

      {error && (
        <Banner variant="warning" className="mt-4">
          {error}
        </Banner>
      )}
      {success && !error && (
        <Banner variant="success" className="mt-4">
          Saved.
        </Banner>
      )}

      <div className="mt-4 space-y-4">
        <Input
          id="questions-per-attempt"
          label="Questions per Level Assessment attempt"
          type="number"
          min={1}
          value={draft.questions_per_attempt}
          onChange={(e) => setDraft({ ...draft, questions_per_attempt: e.target.value })}
        />
        <div>
          <label htmlFor="timing-mode" className="block text-sm font-medium text-neutral-700">
            Level Assessment timing
          </label>
          <select
            id="timing-mode"
            value={draft.timing_mode}
            onChange={(e) => setDraft({ ...draft, timing_mode: e.target.value as TimingMode })}
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm"
          >
            <option value="PER_QUESTION">Per question — countdown resets on each question</option>
            <option value="FIXED_TOTAL">Fixed total — one countdown for the whole exam</option>
          </select>
        </div>
        {draft.timing_mode === 'PER_QUESTION' ? (
          <Input
            id="seconds-per-question"
            label="Seconds per question (countdown timer)"
            type="number"
            min={5}
            value={draft.seconds_per_question}
            onChange={(e) => setDraft({ ...draft, seconds_per_question: e.target.value })}
          />
        ) : (
          <Input
            id="total-exam-minutes"
            label="Total exam time (minutes)"
            type="number"
            min={5}
            value={draft.total_exam_minutes}
            onChange={(e) => setDraft({ ...draft, total_exam_minutes: e.target.value })}
          />
        )}
        <Input
          id="pass-mark-percent"
          label="Pass mark (%) — Level Assessments and course certificates"
          type="number"
          min={0}
          max={100}
          value={draft.pass_mark_percent}
          onChange={(e) => setDraft({ ...draft, pass_mark_percent: e.target.value })}
        />
        <Button onClick={() => void handleSave()} disabled={isSaving}>
          {isSaving ? 'Saving…' : 'Save settings'}
        </Button>
      </div>
    </Card>
  )
}

interface MaxAttemptsDraft {
  levelLimited: boolean
  levelValue: string
  courseLimited: boolean
  courseValue: string
}

const DEFAULT_ATTEMPTS_CAP = '3'

function maxAttemptsDraftFromSettings(settings: OrganizationSettings): MaxAttemptsDraft {
  return {
    levelLimited: settings.max_level_assessment_attempts !== null,
    levelValue: settings.max_level_assessment_attempts !== null ? String(settings.max_level_assessment_attempts) : DEFAULT_ATTEMPTS_CAP,
    courseLimited: settings.max_course_retake_attempts !== null,
    courseValue: settings.max_course_retake_attempts !== null ? String(settings.max_course_retake_attempts) : DEFAULT_ATTEMPTS_CAP,
  }
}

// Unlimited/Limited toggle for each of the two independent attempt caps —
// null (Unlimited) on the wire matches today's behavior exactly, so an org
// that never touches this card keeps working exactly as it always has.
function MaxAttemptsSettingsForm({
  settings,
  onSaved,
}: {
  settings: OrganizationSettings
  onSaved: (updated: OrganizationSettings) => void
}) {
  const [draft, setDraft] = useState<MaxAttemptsDraft>(maxAttemptsDraftFromSettings(settings))
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    setDraft(maxAttemptsDraftFromSettings(settings))
    setError(null)
    setSuccess(false)
  }, [settings])

  async function handleSave() {
    setIsSaving(true)
    setError(null)
    setSuccess(false)
    try {
      const updated = await updateOrganizationSettings(settings.id, {
        max_level_assessment_attempts: draft.levelLimited ? Number(draft.levelValue) : null,
        max_course_retake_attempts: draft.courseLimited ? Number(draft.courseValue) : null,
      })
      onSaved(updated)
      setSuccess(true)
    } catch (err) {
      setError(extractFieldError(err) ?? 'Could not save these limits.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Card className="mt-6 max-w-xl">
      <h2 className="text-sm font-semibold text-neutral-900">Maximum Attempts</h2>
      <p className="mt-1 text-sm text-neutral-500">
        Optional hard caps. Once a learner reaches the limit without passing, the corresponding retake action is
        disabled with an explanation — their Final Status stays Fail either way.
      </p>

      {error && (
        <Banner variant="warning" className="mt-4">
          {error}
        </Banner>
      )}
      {success && !error && (
        <Banner variant="success" className="mt-4">
          Saved.
        </Banner>
      )}

      <div className="mt-4 space-y-5">
        <div className="rounded-lg border border-neutral-200 p-4">
          <p className="text-sm font-medium text-neutral-900">Level Assessment attempts</p>
          <p className="mt-1 text-xs text-neutral-500">
            Counts every attempt at a learner's assigned Level Assessment — the first plus every retake.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <div className="flex overflow-hidden rounded-md border border-neutral-300">
              <button
                type="button"
                onClick={() => setDraft({ ...draft, levelLimited: false })}
                className={`px-3 py-1.5 text-sm transition ${!draft.levelLimited ? 'bg-brand-navy text-white' : 'bg-white text-neutral-600 hover:bg-neutral-50'}`}
              >
                Unlimited
              </button>
              <button
                type="button"
                onClick={() => setDraft({ ...draft, levelLimited: true })}
                className={`px-3 py-1.5 text-sm transition ${draft.levelLimited ? 'bg-brand-navy text-white' : 'bg-white text-neutral-600 hover:bg-neutral-50'}`}
              >
                Limited to X attempts
              </button>
            </div>
            {draft.levelLimited && (
              <input
                type="number"
                min={1}
                value={draft.levelValue}
                onChange={(e) => setDraft({ ...draft, levelValue: e.target.value })}
                className="w-20 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
              />
            )}
          </div>
        </div>

        <div className="rounded-lg border border-neutral-200 p-4">
          <p className="text-sm font-medium text-neutral-900">Course retake attempts</p>
          <p className="mt-1 text-xs text-neutral-500">
            Counts only the "Retake Course" action itself, not the original attempt.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <div className="flex overflow-hidden rounded-md border border-neutral-300">
              <button
                type="button"
                onClick={() => setDraft({ ...draft, courseLimited: false })}
                className={`px-3 py-1.5 text-sm transition ${!draft.courseLimited ? 'bg-brand-navy text-white' : 'bg-white text-neutral-600 hover:bg-neutral-50'}`}
              >
                Unlimited
              </button>
              <button
                type="button"
                onClick={() => setDraft({ ...draft, courseLimited: true })}
                className={`px-3 py-1.5 text-sm transition ${draft.courseLimited ? 'bg-brand-navy text-white' : 'bg-white text-neutral-600 hover:bg-neutral-50'}`}
              >
                Limited to X attempts
              </button>
            </div>
            {draft.courseLimited && (
              <input
                type="number"
                min={1}
                value={draft.courseValue}
                onChange={(e) => setDraft({ ...draft, courseValue: e.target.value })}
                className="w-20 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
              />
            )}
          </div>
        </div>

        <Button onClick={() => void handleSave()} disabled={isSaving}>
          {isSaving ? 'Saving…' : 'Save limits'}
        </Button>
      </div>
    </Card>
  )
}

const FREQUENCY_OPTIONS: { value: ReminderFrequency; label: string }[] = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'fortnightly', label: 'Fortnightly' },
  { value: 'monthly', label: 'Monthly' },
]

function formatLastSent(value: string | null): string {
  return value ? new Date(value).toLocaleString() : 'Never sent yet'
}

interface ReminderDraft {
  logged_in_inactive_reminder_enabled: boolean
  logged_in_inactive_reminder_frequency: ReminderFrequency
  never_logged_in_reminder_enabled: boolean
  never_logged_in_reminder_frequency: ReminderFrequency
}

function reminderDraftFromSettings(settings: OrganizationSettings): ReminderDraft {
  return {
    logged_in_inactive_reminder_enabled: settings.logged_in_inactive_reminder_enabled,
    logged_in_inactive_reminder_frequency: settings.logged_in_inactive_reminder_frequency,
    never_logged_in_reminder_enabled: settings.never_logged_in_reminder_enabled,
    never_logged_in_reminder_frequency: settings.never_logged_in_reminder_frequency,
  }
}

// Two independent, visually distinct reminder configurations — deliberately
// not merged into a single control, since they target different audiences
// (staff who've logged in but never engaged, vs. staff who've never logged
// in at all) with different email content. Sent by the send_inactivity_reminders
// management command, run once daily via a cPanel Cron Job (this host has no
// background task worker) — see org_settings/services.py.
function ReminderSettingsForm({
  settings,
  onSaved,
}: {
  settings: OrganizationSettings
  onSaved: (updated: OrganizationSettings) => void
}) {
  const [draft, setDraft] = useState<ReminderDraft>(reminderDraftFromSettings(settings))
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    setDraft(reminderDraftFromSettings(settings))
    setError(null)
    setSuccess(false)
  }, [settings])

  async function handleSave() {
    setIsSaving(true)
    setError(null)
    setSuccess(false)
    try {
      const updated = await updateOrganizationSettings(settings.id, draft)
      onSaved(updated)
      setSuccess(true)
    } catch (err) {
      setError(extractFieldError(err) ?? 'Could not save these reminder settings.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Card className="mt-6 max-w-xl">
      <h2 className="text-sm font-semibold text-neutral-900">Inactivity Reminder Emails</h2>
      <p className="mt-1 text-sm text-neutral-500">
        Automatically nudge staff who aren't engaging with their assigned training. Each reminder below is
        independent — turn either on and set its own schedule.
      </p>

      {error && (
        <Banner variant="warning" className="mt-4">
          {error}
        </Banner>
      )}
      {success && !error && (
        <Banner variant="success" className="mt-4">
          Saved.
        </Banner>
      )}

      <div className="mt-4 space-y-5">
        <div className="rounded-lg border border-neutral-200 p-4">
          <label className="flex items-center gap-2 text-sm font-medium text-neutral-900">
            <input
              type="checkbox"
              checked={draft.logged_in_inactive_reminder_enabled}
              onChange={(e) => setDraft({ ...draft, logged_in_inactive_reminder_enabled: e.target.checked })}
            />
            Logged in, but hasn't started training
          </label>
          <p className="mt-1 text-xs text-neutral-500">
            For staff who have logged in at least once but have zero completed courses and zero Level Assessment
            attempts.
          </p>
          <div className="mt-3">
            <label htmlFor="logged-in-inactive-frequency" className="block text-xs font-medium text-neutral-500">
              Frequency
            </label>
            <select
              id="logged-in-inactive-frequency"
              disabled={!draft.logged_in_inactive_reminder_enabled}
              value={draft.logged_in_inactive_reminder_frequency}
              onChange={(e) =>
                setDraft({ ...draft, logged_in_inactive_reminder_frequency: e.target.value as ReminderFrequency })
              }
              className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm disabled:bg-neutral-50 disabled:text-neutral-400"
            >
              {FREQUENCY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <p className="mt-2 text-xs text-neutral-400">
            Last sent: {formatLastSent(settings.logged_in_inactive_last_sent_at)}
          </p>
        </div>

        <div className="rounded-lg border border-neutral-200 p-4">
          <label className="flex items-center gap-2 text-sm font-medium text-neutral-900">
            <input
              type="checkbox"
              checked={draft.never_logged_in_reminder_enabled}
              onChange={(e) => setDraft({ ...draft, never_logged_in_reminder_enabled: e.target.checked })}
            />
            Never logged in
          </label>
          <p className="mt-1 text-xs text-neutral-500">
            For staff who have never logged in at all — a fresh temporary password is issued if their original one
            is still unclaimed.
          </p>
          <div className="mt-3">
            <label htmlFor="never-logged-in-frequency" className="block text-xs font-medium text-neutral-500">
              Frequency
            </label>
            <select
              id="never-logged-in-frequency"
              disabled={!draft.never_logged_in_reminder_enabled}
              value={draft.never_logged_in_reminder_frequency}
              onChange={(e) =>
                setDraft({ ...draft, never_logged_in_reminder_frequency: e.target.value as ReminderFrequency })
              }
              className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm disabled:bg-neutral-50 disabled:text-neutral-400"
            >
              {FREQUENCY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <p className="mt-2 text-xs text-neutral-400">
            Last sent: {formatLastSent(settings.never_logged_in_last_sent_at)}
          </p>
        </div>

        <Button onClick={() => void handleSave()} disabled={isSaving}>
          {isSaving ? 'Saving…' : 'Save reminder settings'}
        </Button>
      </div>
    </Card>
  )
}

export function OrganizationSettingsPage() {
  const { user } = useAuth()
  const organization = user?.organization
  const isPlatformAdmin = isPlatformAdminRole(user?.role)

  const [settingsList, setSettingsList] = useState<OrganizationSettings[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)

  useEffect(() => {
    fetchOrganizationSettingsList()
      .then((list) => {
        setSettingsList(list)
        setSelectedId((prev) => prev ?? list[0]?.id ?? null)
      })
      .catch(() => setLoadError('Could not load organization settings.'))
  }, [])

  function applyUpdate(updated: OrganizationSettings) {
    setSettingsList((prev) => prev?.map((s) => (s.id === updated.id ? updated : s)) ?? null)
  }

  const selected = settingsList?.find((s) => s.id === selectedId) ?? null

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Organization Settings</h1>

      {!organization ? (
        <Card className="mt-6">
          <p className="text-sm text-neutral-500">
            {isPlatformAdmin
              ? 'Platform admins are not scoped to a single organization — manage per-organization course access from a course’s access grants.'
              : 'No organization is associated with your account.'}
          </p>
        </Card>
      ) : (
        <Card className="mt-6 flex items-start gap-5">
          {organization.logo ? (
            <img src={organization.logo} alt="" className="h-16 w-16 rounded-lg object-contain" />
          ) : (
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg bg-brand-navy/10 text-lg font-semibold text-brand-navy">
              {organization.name.slice(0, 2).toUpperCase()}
            </div>
          )}
          <div>
            <p className="text-base font-semibold text-neutral-900">{organization.name}</p>
            <p className="text-sm text-neutral-500">/{organization.slug}</p>
            <Badge variant={organization.is_active ? 'navy' : 'neutral'} className="mt-3">
              {organization.is_active ? 'Active' : 'Inactive'}
            </Badge>
          </div>
        </Card>
      )}

      {loadError && (
        <Banner variant="warning" className="mt-6">
          {loadError}
        </Banner>
      )}

      {/* PLATFORM_ADMIN edits any organization's settings, one at a time — same
          "list everything, pick a slot" pattern as CertificateTemplatesPage's
          organization selector. An ORG_ADMIN's list only ever has their own
          organization's single row, so no selector is shown for them. */}
      {isPlatformAdmin && settingsList && settingsList.length > 1 && (
        <div className="mt-6 max-w-xl">
          <label htmlFor="org-settings-select" className="block text-sm font-medium text-neutral-700">
            Organization
          </label>
          <select
            id="org-settings-select"
            className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm"
            value={selectedId ?? ''}
            onChange={(e) => setSelectedId(Number(e.target.value))}
          >
            {settingsList.map((s) => (
              <option key={s.id} value={s.id}>
                {s.organization.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {selected && <SettingsForm settings={selected} onSaved={applyUpdate} />}
      {selected && <MaxAttemptsSettingsForm settings={selected} onSaved={applyUpdate} />}
      {selected && <ReminderSettingsForm settings={selected} onSaved={applyUpdate} />}
    </div>
  )
}
