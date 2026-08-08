import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import loginHero from '../assets/login-hero.jpg'
import siorikLogoIcon from '../img/siorik_logo_icon.png'
import { ApiError } from '../lib/apiClient'
import { useAuth } from '../context/AuthContext'
import { Button } from '../components/ui/Button'

interface LocationState {
  from?: { pathname: string }
}

const FOCUS_RING = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-navy focus-visible:ring-offset-1'

function CreamField({
  id,
  label,
  type,
  autoComplete,
  value,
  onChange,
}: {
  id: string
  label: string
  type: 'email' | 'password'
  autoComplete: string
  value: string
  onChange: (value: string) => void
}) {
  const [show, setShow] = useState(false)
  const isPassword = type === 'password'
  const inputType = isPassword ? (show ? 'text' : 'password') : type

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-semibold text-neutral-800">
        {label}
      </label>
      <div className="relative mt-1.5">
        <input
          id={id}
          type={inputType}
          autoComplete={autoComplete}
          required
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`block w-full rounded-2xl border border-brand-gold/30 bg-[#fbf1d9] px-3.5 py-2.5 text-sm text-neutral-900 shadow-sm transition placeholder:text-neutral-400 focus:border-brand-navy focus:ring-2 focus:ring-brand-navy focus:outline-none ${isPassword ? 'pr-11' : ''}`}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            aria-label={show ? 'Hide password' : 'Show password'}
            aria-pressed={show}
            className={`absolute inset-y-0 right-0 flex items-center rounded-r-2xl px-3 text-neutral-500 hover:text-neutral-700 ${FOCUS_RING}`}
          >
            {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        )}
      </div>
    </div>
  )
}

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (user) {
    const from = (location.state as LocationState | null)?.from?.pathname ?? '/dashboard'
    return <Navigate to={from} replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(email, password)
      const from = (location.state as LocationState | null)?.from?.pathname ?? '/dashboard'
      navigate(from, { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('Incorrect email or password.')
      } else {
        setError('Something went wrong. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="relative min-h-screen w-full overflow-x-hidden bg-brand-navy">
      {/* Full-bleed hero background — desktop only. Below the tablet breakpoint the image can't
          reflow sensibly, so mobile falls back to the plain brand-navy background instead.
          w-full/h-full (not the image's intrinsic 2555px) keep this fluid at every width. */}
      <img
        src={loginHero}
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 hidden h-full w-full object-cover md:block"
      />

      {/* Single sign-in card instance: a normal-flow, centered stack (with the compact mobile
          logo) below md, repositioned via absolute inset-0 + flexbox at md and up. Flexbox
          (justify-end/items-center), not a fixed right-N% offset paired with a separately fixed
          max-width, does the right-anchoring — it reflows with the container's actual width at
          every intermediate size instead of only being correct at the exact breakpoints it was
          tuned for. Rendered once (not duplicated per breakpoint) so the form's field ids stay
          unique in the DOM. */}
      <div className="relative z-10 flex min-h-screen w-full flex-col items-center justify-center gap-8 px-6 py-10 md:absolute md:inset-0 md:min-h-0 md:flex-row md:justify-end md:px-6 md:py-6 lg:px-10 xl:px-16">
        <img src={siorikLogoIcon} alt="Siorik Consultancy" className="h-16 w-16 object-contain md:hidden" />

        <div className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-2xl md:bg-white/95 md:backdrop-blur-sm">
          <h2 className="text-2xl font-bold text-brand-navy">Sign In</h2>
          <p className="mt-1 text-sm text-neutral-500">Access your learning dashboard</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-5">
            <CreamField id="email" label="Email" type="email" autoComplete="email" value={email} onChange={setEmail} />

            <CreamField
              id="password"
              label="Password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={setPassword}
            />

            <div className="flex items-center justify-between">
              <label htmlFor="remember-me" className="flex items-center gap-2 text-sm text-neutral-600">
                <input
                  id="remember-me"
                  type="checkbox"
                  className={`h-4 w-4 rounded border-neutral-300 accent-brand-navy ${FOCUS_RING}`}
                />
                Remember me
              </label>
              <button type="button" className={`rounded text-sm font-medium text-brand-navy hover:underline ${FOCUS_RING}`}>
                Forgot Password?
              </button>
            </div>

            {error && (
              <p role="alert" className="text-sm text-red-600">
                {error}
              </p>
            )}

            <Button
              type="submit"
              disabled={isSubmitting}
              className="w-full !rounded-2xl py-2.5 transition-colors duration-[350ms] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
            >
              {isSubmitting ? 'Signing in…' : 'Sign In'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
