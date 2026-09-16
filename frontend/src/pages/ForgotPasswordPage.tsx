import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import siorikLogoIcon from '../img/siorik_logo_icon.png'
import { requestPasswordReset } from '../lib/apiClient'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

// Always shows the same generic confirmation regardless of whether the email
// matched an account — mirrors the backend's PasswordResetRequestView, which
// never reveals account existence either. See accounts/views.py.
export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSubmitting(true)
    try {
      await requestPasswordReset(email)
    } catch {
      // Intentionally ignored — the confirmation message is shown either
      // way so this endpoint can't be used to probe for valid emails.
    } finally {
      setIsSubmitting(false)
      setSubmitted(true)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex min-h-screen items-center justify-center bg-neutral-50 px-4 py-12">
      <div className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-2xl">
        <div className="flex items-center gap-3">
          <img src={siorikLogoIcon} alt="Siorik Consultancy" className="h-9 w-9 object-contain" />
          <span className="text-xs font-semibold tracking-[0.2em] text-brand-navy uppercase">Siorik Consultancy</span>
        </div>

        <h2 className="mt-6 text-xl font-semibold text-neutral-900">Forgot password?</h2>

        {submitted ? (
          <>
            <p className="mt-1 text-sm text-neutral-600">
              If an account exists for <strong>{email}</strong>, we've sent a link to reset the password.
              Check the inbox (and spam folder).
            </p>
            <Link to="/login" className="mt-5 inline-block text-sm font-medium text-brand-navy hover:underline">
              Back to login
            </Link>
          </>
        ) : (
          <>
            <p className="mt-1 text-sm text-neutral-500">
              Enter the email on the account and we'll send a link to reset the password.
            </p>

            <form onSubmit={handleSubmit} className="mt-5 space-y-4">
              <Input
                id="email"
                label="Email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />

              <Button type="submit" disabled={isSubmitting} className="w-full">
                {isSubmitting ? 'Sending…' : 'Send reset link'}
              </Button>

              <Link to="/login" className="block text-center text-sm font-medium text-brand-navy hover:underline">
                Back to login
              </Link>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
