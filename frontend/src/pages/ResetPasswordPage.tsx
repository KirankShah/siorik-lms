import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import siorikLogoIcon from '../img/siorik_logo_icon.png'
import { ApiError, confirmPasswordReset } from '../lib/apiClient'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

const MIN_PASSWORD_LENGTH = 8
const RULES_MESSAGE = `Password must be at least ${MIN_PASSWORD_LENGTH} characters and include at least 1 letter and 1 number.`

function passwordMeetsRules(password: string): boolean {
  return password.length >= MIN_PASSWORD_LENGTH && /[A-Za-z]/.test(password) && /[0-9]/.test(password)
}

// Landed on from the link in accounts.services.send_password_reset_email —
// uid/token identify the account and are validated server-side on submit
// (PasswordResetConfirmSerializer), not here.
export function ResetPasswordPage() {
  const { uid, token } = useParams<{ uid: string; token: string }>()

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)

    if (!uid || !token) {
      setError('This password reset link is invalid or has expired.')
      return
    }
    if (!passwordMeetsRules(newPassword)) {
      setError(RULES_MESSAGE)
      return
    }
    if (newPassword !== confirmPassword) {
      setError('New password and confirmation do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      await confirmPasswordReset(uid, token, newPassword)
      setSuccess(true)
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const body = err.body as { new_password?: string[]; detail?: string } | null
        setError(body?.new_password?.[0] ?? body?.detail ?? 'Could not reset your password.')
      } else {
        setError('Something went wrong. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex min-h-screen items-center justify-center bg-neutral-50 px-4 py-12">
      <div className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-2xl">
        <div className="flex items-center gap-3">
          <img src={siorikLogoIcon} alt="Siorik Consultancy" className="h-9 w-9 object-contain" />
          <span className="text-xs font-semibold tracking-[0.2em] text-brand-navy uppercase">Siorik Consultancy</span>
        </div>

        <h2 className="mt-6 text-xl font-semibold text-neutral-900">Reset your password</h2>

        {success ? (
          <>
            <p className="mt-1 text-sm text-neutral-600">Your password has been reset. You can now log in.</p>
            <Link to="/login" className="mt-5 inline-block text-sm font-medium text-brand-navy hover:underline">
              Go to login
            </Link>
          </>
        ) : (
          <>
            <p className="mt-1 text-sm text-neutral-500">Choose a new password for the account.</p>

            <ul className="mt-4 space-y-1 rounded-lg bg-neutral-50 px-4 py-3 text-xs text-neutral-600">
              <li>• Minimum {MIN_PASSWORD_LENGTH} characters</li>
              <li>• At least 1 letter and 1 number</li>
            </ul>

            <form onSubmit={handleSubmit} className="mt-5 space-y-4">
              <Input
                id="new-password"
                label="New Password"
                type="password"
                autoComplete="new-password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />

              <Input
                id="confirm-password"
                label="Confirm Password"
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
                {isSubmitting ? 'Resetting…' : 'Reset password'}
              </Button>

              <Link to="/forgot-password" className="block text-center text-sm font-medium text-brand-navy hover:underline">
                Request a new link
              </Link>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
