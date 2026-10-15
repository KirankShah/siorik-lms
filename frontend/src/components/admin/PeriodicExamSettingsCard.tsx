import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Input } from '../ui/Input'
import { ApiError } from '../../lib/apiClient'
import { fetchPeriodicExamSettings, updatePeriodicExamSettings } from '../../lib/periodicExamsApi'
import type { PeriodicExamFrequency, PeriodicExamSettings } from '../../types/periodicExams'

export function PeriodicExamSettingsCard() {
  const [settings, setSettings] = useState<PeriodicExamSettings | null>(null)
  const [isEnabled, setIsEnabled] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [reminderDays, setReminderDays] = useState('7, 2')

  useEffect(() => {
    fetchPeriodicExamSettings()
      .then((value) => {
        setSettings(value)
        setReminderDays(value.reminder_days_before_end.join(', '))
      })
      .catch((requestError) => {
        if (requestError instanceof ApiError && requestError.status === 404) setIsEnabled(false)
        else setError('Could not load Periodic Exam settings.')
      })
  }, [])

  function updateNumber(field: keyof PeriodicExamSettings, value: string) {
    if (settings) setSettings({ ...settings, [field]: Number(value) })
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!settings) return
    setError(null)
    setSuccess(null)
    const days = reminderDays.split(',').map((value) => Number(value.trim()))
    setSaving(true)
    try {
      const updated = await updatePeriodicExamSettings({
        frequency: settings.frequency,
        questions_per_exam: settings.questions_per_exam,
        pass_mark_percent: settings.pass_mark_percent,
        seconds_per_question: settings.seconds_per_question,
        max_attempts_per_cycle: settings.max_attempts_per_cycle,
        reminders_enabled: settings.reminders_enabled,
        reminder_days_before_end: days,
      })
      setSettings(updated)
      setReminderDays(updated.reminder_days_before_end.join(', '))
      setSuccess('Periodic Exam settings saved for the next cycle.')
    } catch (requestError) {
      setError(
        requestError instanceof ApiError && requestError.status === 400
          ? 'Check the values and reminder days, then try again.'
          : 'Could not save Periodic Exam settings.',
      )
    } finally {
      setSaving(false)
    }
  }

  if (!isEnabled) return null

  return (
    <Card className="mt-6">
      <h2 className="text-sm font-semibold text-neutral-900">Periodic Exam Settings</h2>
      <p className="mt-1 text-xs text-neutral-500">Changes apply from the next cycle only.</p>
      {settings && (
        <div className="mt-4 rounded-md bg-neutral-50 p-3 text-xs text-neutral-600">
          <p className="font-medium text-neutral-700">Current question bank by level</p>
          <p className="mt-1">
            {settings.question_counts.map((item) => `${item.level_display}: ${item.question_count}`).join(' · ')}
          </p>
        </div>
      )}
      {settings?.current_cycle && (
        <div className="mt-4 rounded-md bg-neutral-50 p-3 text-sm text-neutral-700">
          Current cycle: <span className="font-medium">{settings.current_cycle.display_label}</span>{' '}
          ({settings.current_cycle.start_date_ad} to {settings.current_cycle.end_date_ad})
          <span className="mt-1 block text-xs text-neutral-500">
            {settings.current_cycle.questions_per_exam} questions · {settings.current_cycle.pass_mark_percent}% pass mark ·{' '}
            {settings.current_cycle.seconds_per_question} seconds each · {settings.current_cycle.max_attempts_per_cycle} attempts
          </span>
        </div>
      )}
      {!settings && !error ? (
        <p className="mt-4 text-sm text-neutral-500">Loading…</p>
      ) : settings ? (
        <form onSubmit={handleSubmit} className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label htmlFor="periodic-frequency" className="block text-sm font-medium text-neutral-700">Frequency</label>
            <select
              id="periodic-frequency"
              value={settings.frequency}
              onChange={(event) => setSettings({ ...settings, frequency: event.target.value as PeriodicExamFrequency })}
              className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm"
            >
              <option value="MONTHLY">Monthly</option>
              <option value="QUARTERLY">Quarterly</option>
              <option value="HALF_YEARLY">Half-yearly</option>
              <option value="YEARLY">Yearly</option>
            </select>
            {settings.pending_frequency && (
              <p className="mt-1 text-xs text-neutral-500">Pending: {settings.pending_frequency.replace('_', ' ').toLowerCase()}</p>
            )}
          </div>
          <Input id="periodic-questions" label="Questions per exam" type="number" min={1} value={settings.questions_per_exam} onChange={(event) => updateNumber('questions_per_exam', event.target.value)} />
          <Input id="periodic-pass-mark" label="Pass mark (%)" type="number" min={0} max={100} value={settings.pass_mark_percent} onChange={(event) => updateNumber('pass_mark_percent', event.target.value)} />
          <Input id="periodic-seconds" label="Seconds per question" type="number" min={5} value={settings.seconds_per_question} onChange={(event) => updateNumber('seconds_per_question', event.target.value)} />
          <Input id="periodic-attempts" label="Maximum attempts per cycle" type="number" min={1} value={settings.max_attempts_per_cycle} onChange={(event) => updateNumber('max_attempts_per_cycle', event.target.value)} />
          <Input id="periodic-reminder-days" label="Reminder days before end (comma-separated)" value={reminderDays} onChange={(event) => setReminderDays(event.target.value)} />
          <label className="flex items-center gap-2 text-sm text-neutral-700">
            <input type="checkbox" checked={settings.reminders_enabled} onChange={(event) => setSettings({ ...settings, reminders_enabled: event.target.checked })} />
            Send Periodic Exam reminders
          </label>
          <div className="md:col-span-2">
            {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
            {success && <p className="mb-3 text-sm text-emerald-700">{success}</p>}
            <Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save settings'}</Button>
          </div>
        </form>
      ) : (
        <p className="mt-4 text-sm text-red-600">{error}</p>
      )}
    </Card>
  )
}
