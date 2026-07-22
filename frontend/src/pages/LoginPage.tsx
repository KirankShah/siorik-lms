import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import siorikLogoIcon from '../img/siorik_logo_icon.png'
import siorikLogoWatermark from '../img/siorik_logo_320.png'
import { ApiError } from '../lib/apiClient'
import { useAuth } from '../context/AuthContext'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

interface LocationState {
  from?: { pathname: string }
}

const SCOPE_PILLS = ['Compliance', 'Credit', 'Operations', 'Leadership']

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
    <div className="flex min-h-screen bg-white">
      {/* Left panel — hidden below the tablet breakpoint */}
      <div className="relative hidden w-[45%] shrink-0 overflow-hidden bg-gradient-to-br from-brand-navy to-brand-navy-light md:flex md:flex-col md:px-12 md:py-14">
        {/* Oversized, low-opacity watermark of the logo mark, bleeding off the
            panel's bottom-right corner so it reads as background texture. */}
        <img
          src={siorikLogoWatermark}
          alt=""
          aria-hidden="true"
          className="pointer-events-none absolute -right-40 -bottom-40 h-[36rem] w-[36rem] object-contain opacity-[0.07] select-none"
        />

        <div className="relative z-10 flex flex-col">
          <div className="flex items-center gap-3">
            <img src={siorikLogoIcon} alt="Siorik Consultancy" className="h-11 w-11 shrink-0 object-contain" />
            <span className="text-xs font-semibold tracking-[0.2em] text-white/90 uppercase">Siorik Consultancy</span>
          </div>

          <h1 className="mt-10 max-w-md text-3xl font-semibold text-white md:text-[2.25rem] md:leading-[1.15]">
            Compounding Interest, for Your People.
          </h1>

          <p className="mt-4 max-w-sm text-base text-white/75">
            Strong institutions are built on strong people — this platform helps you build both.
          </p>

          <div className="mt-6 flex flex-wrap gap-2">
            {SCOPE_PILLS.map((scope) => (
              <Badge key={scope} variant="dark">
                {scope}
              </Badge>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel — the login form */}
      <div className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm">
          <h2 className="text-xl font-semibold text-neutral-900">Sign in</h2>
          <p className="mt-1 text-sm text-neutral-500">Access your learning dashboard</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <Input
              id="email"
              label="Email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />

            <Input
              id="password"
              label="Password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />

            {error && (
              <p role="alert" className="text-sm text-red-600">
                {error}
              </p>
            )}

            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
