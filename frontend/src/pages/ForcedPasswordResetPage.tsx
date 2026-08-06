import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import siorikLogoIcon from '../img/siorik_logo_icon.png'
import { ApiError, setPassword } from '../lib/apiClient'
import { useAuth } from '../context/AuthContext'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

export function ForcedPasswordResetPage() {
  const { user, refreshUser } = useAuth()
  const navigate = useNavigate()

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Already reset (or not a temp-password account) — nothing to do here.
  if (user && !user.must_reset_password) {
    return <Navigate to="/dashboard" replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)

    if (newPassword !== confirmPassword) {
      setError('New password and confirmation do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      await setPassword(currentPassword, newPassword)
      await refreshUser()
      navigate('/dashboard', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const body = err.body as { current_password?: string[]; new_password?: string[]; detail?: string } | null
        setError(body?.current_password?.[0] ?? body?.new_password?.[0] ?? body?.detail ?? 'Could not update your password.')
      } else {
        setError('Something went wrong. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-50 px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-3">
          <img src={siorikLogoIcon} alt="Siorik Consultancy" className="h-9 w-9 object-contain" />
          <span className="text-xs font-semibold tracking-[0.2em] text-brand-navy uppercase">Siorik Consultancy</span>
        </div>

        <h1 className="mt-8 text-xl font-semibold text-neutral-900">Set your password</h1>
        <p className="mt-1 text-sm text-neutral-500">
          This account was created with a temporary password. Choose your own before continuing.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <Input
            id="current-password"
            label="Temporary password"
            type="password"
            autoComplete="current-password"
            required
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
          />

          <Input
            id="new-password"
            label="New password"
            type="password"
            autoComplete="new-password"
            required
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />

          <Input
            id="confirm-password"
            label="Confirm new password"
            type="password"
            autoComplete="new-password"
            required
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />

          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}

          <Button type="submit" disabled={isSubmitting} className="w-full">
            {isSubmitting ? 'Saving…' : 'Set password and continue'}
          </Button>
        </form>
      </div>
    </div>
  )
}
