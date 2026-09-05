import { useEffect, useState } from 'react'
import { Button } from '../ui/Button'
import { useAuth } from '../../context/AuthContext'
import { ApiError } from '../../lib/apiClient'
import { fetchNarrationsForSlide, generateSlideNarration } from '../../lib/narrationApi'
import { isPlatformAdminRole } from '../../lib/roles'
import type { NarrationLanguage } from '../../types/auth'
import type { SlideNarration } from '../../types/narration'

interface NarrationPanelProps {
  slideId: number
}

const LANGUAGES: { code: NarrationLanguage; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'ne', label: 'Nepali' },
]

// The backend reports the actual failure reason (missing credentials, no
// narratable content, an upstream Claude/Azure error, ...) as {detail: "..."}
// or {field: [...]} — surface that instead of a one-size-fits-all message,
// or this exact class of bug (wrong root cause reported to the user) is
// exactly what makes generation failures hard to diagnose from the UI alone.
function extractErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.body && typeof err.body === 'object') {
    const value = Object.values(err.body as Record<string, unknown>)[0]
    if (typeof value === 'string') return value
    if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
  }
  return fallback
}

// Generation authoring UI, restricted to PLATFORM_ADMIN — hiding this panel
// for other roles is a UX nicety only; the real restriction is enforced
// server-side (narration.views.SlideNarrationViewSet.get_permissions), since
// a hidden UI control is not a permission check.
export function NarrationPanel({ slideId }: NarrationPanelProps) {
  const { user } = useAuth()
  const [narrations, setNarrations] = useState<SlideNarration[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [generatingLanguage, setGeneratingLanguage] = useState<NarrationLanguage | null>(null)
  const [expandedLanguage, setExpandedLanguage] = useState<NarrationLanguage | null>(null)

  function load() {
    fetchNarrationsForSlide(slideId)
      .then(setNarrations)
      .catch(() => setError('Could not load narration status.'))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [slideId])

  if (!isPlatformAdminRole(user?.role)) return null

  async function handleGenerate(language: NarrationLanguage) {
    setGeneratingLanguage(language)
    setError(null)
    try {
      const narration = await generateSlideNarration(slideId, language)
      setNarrations((prev) => [...(prev ?? []).filter((n) => n.language !== language), narration])
    } catch (err) {
      setError(extractErrorMessage(err, 'Narration generation failed. Please try again.'))
    } finally {
      setGeneratingLanguage(null)
    }
  }

  return (
    <div className="rounded-xl border border-neutral-200 p-4">
      <h3 className="text-sm font-semibold text-neutral-900">Narration</h3>
      <p className="mt-0.5 text-xs text-neutral-500">
        AI-generated spoken narration of this slide's content, per language. Generating overwrites any existing
        script and audio for that language only.
      </p>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <div className="mt-3 space-y-3">
        {LANGUAGES.map(({ code, label }) => {
          const narration = narrations?.find((n) => n.language === code) ?? null
          const isGenerating = generatingLanguage === code
          const isExpanded = expandedLanguage === code

          return (
            <div key={code} className="rounded-lg border border-neutral-200 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-neutral-900">{label}</span>
                  {narration ? (
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                      Generated
                    </span>
                  ) : (
                    <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-500">
                      Not yet generated
                    </span>
                  )}
                </div>
                <Button
                  size="sm"
                  variant={narration ? 'outline' : 'primary'}
                  disabled={isGenerating}
                  onClick={() => void handleGenerate(code)}
                >
                  {isGenerating ? 'Generating…' : narration ? 'Regenerate' : 'Generate'}
                </Button>
              </div>

              {isGenerating && (
                <p className="mt-2 text-xs text-neutral-500">
                  Writing the script and synthesizing audio — this can take up to a minute.
                </p>
              )}

              {narration && !isGenerating && (
                <div className="mt-2">
                  <audio controls src={narration.audio_file ?? undefined} className="h-9 w-full" />
                  <div className="mt-1.5 flex items-center justify-between text-xs text-neutral-400">
                    <span>
                      {narration.voice_name}
                      {narration.generated_by_name ? ` · by ${narration.generated_by_name}` : ''}
                    </span>
                    <button
                      type="button"
                      onClick={() => setExpandedLanguage(isExpanded ? null : code)}
                      className="font-medium text-brand-navy hover:underline"
                    >
                      {isExpanded ? 'Hide script' : 'View script'}
                    </button>
                  </div>
                  {isExpanded && (
                    <p className="mt-2 rounded-md bg-neutral-50 p-2 text-xs whitespace-pre-wrap text-neutral-700">
                      {narration.script_text}
                    </p>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
