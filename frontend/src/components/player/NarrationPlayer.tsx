import { useEffect, useRef, useState } from 'react'
import { FileText, Pause, Play } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import type { NarrationLanguage } from '../../types/auth'
import type { SlideNarration } from '../../types/narration'

interface NarrationPlayerProps {
  narrations: SlideNarration[]
}

const LANGUAGE_LABEL: Record<NarrationLanguage, string> = { en: 'English', ne: 'Nepali' }
const PLAYBACK_RATES = [0.75, 1, 1.25, 1.5]

// Fixed collapsed-bar height (h-12, 48px) + the mt-2 gap above it (8px) +
// slack for the optional single-line fallback note below it (~18px) —
// ContentSlidePlayer subtracts this from SlideCanvas's fullscreen budget so
// the bar (and, when shown, the fallback note) never eats into the canvas
// box. The transcript panel pops up `absolute` above the bar instead of
// pushing layout, so it never needs to be accounted for here regardless of
// script length.
export const NARRATION_BAR_FULLSCREEN_RESERVE_PX = 74

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds)) return '0:00'
  const total = Math.floor(seconds)
  const minutes = Math.floor(total / 60)
  const secs = total % 60
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

// Supplementary aid, rendered whenever a CONTENT slide has at least one
// SlideNarration — never touches SlidePlayer's dwell timer or completion
// gating. Lives inside ContentSlidePlayer, so it renders through the exact
// same component tree the standard and fullscreen views both already share
// (see ContentSlidePlayer/CourseDetailPage — there's only one slidePlayerNode,
// reused as-is by both).
export function NarrationPlayer({ narrations }: NarrationPlayerProps) {
  const { user, updateNarrationLanguage } = useAuth()
  const preferredLanguage: NarrationLanguage = user?.preferred_narration_language ?? 'en'
  const bothAvailable = narrations.length === 2

  const [selectedLanguage, setSelectedLanguage] = useState<NarrationLanguage>(() => {
    const preferred = narrations.find((n) => n.language === preferredLanguage)
    return preferred ? preferred.language : narrations[0].language
  })
  const [showTranscript, setShowTranscript] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [playbackRate, setPlaybackRate] = useState(1)
  const audioRef = useRef<HTMLAudioElement>(null)

  const activeNarration = narrations.find((n) => n.language === selectedLanguage) ?? narrations[0]
  const isFallback = !bothAvailable && selectedLanguage !== preferredLanguage

  // A slide switch (new narrations array) re-resolves the preferred/fallback
  // language and resets the transport — a manual toggle click (below) is the
  // only other way selectedLanguage changes, and that intentionally isn't in
  // this dependency list.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const preferred = narrations.find((n) => n.language === preferredLanguage)
    setSelectedLanguage(preferred ? preferred.language : narrations[0].language)
    setIsPlaying(false)
    setCurrentTime(0)
    setDuration(0)
  }, [narrations])

  function handleToggleLanguage(language: NarrationLanguage) {
    if (language === selectedLanguage) return
    setSelectedLanguage(language)
    setIsPlaying(false)
    setCurrentTime(0)
    setDuration(0)
    if (language !== preferredLanguage) void updateNarrationLanguage(language)
  }

  function togglePlay() {
    const audio = audioRef.current
    if (!audio) return
    if (isPlaying) {
      audio.pause()
    } else {
      void audio.play()
    }
  }

  function handleSeek(e: React.ChangeEvent<HTMLInputElement>) {
    const audio = audioRef.current
    const value = Number(e.target.value)
    setCurrentTime(value)
    if (audio) audio.currentTime = value
  }

  function handleRateChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const rate = Number(e.target.value)
    setPlaybackRate(rate)
    if (audioRef.current) audioRef.current.playbackRate = rate
  }

  return (
    <div className="relative">
      {showTranscript && (
        <div className="absolute bottom-full left-0 mb-2 max-h-56 w-full overflow-y-auto rounded-lg border border-neutral-200 bg-white p-3 text-xs whitespace-pre-wrap text-neutral-700 shadow-lg">
          {activeNarration.script_text}
        </div>
      )}

      <div className="flex h-12 items-center gap-3 rounded-lg border border-neutral-200 bg-white px-3 shadow-sm">
        <button
          type="button"
          onClick={togglePlay}
          aria-label={isPlaying ? 'Pause narration' : 'Play narration'}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-navy text-white transition hover:bg-brand-navy-light"
        >
          {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 translate-x-0.5" />}
        </button>

        <audio
          key={activeNarration.id}
          ref={audioRef}
          src={activeNarration.audio_file ?? undefined}
          preload="metadata"
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={() => setIsPlaying(false)}
          onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
          onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
          className="hidden"
        />

        <span className="w-9 shrink-0 text-right text-xs tabular-nums text-neutral-500">
          {formatTime(currentTime)}
        </span>
        <input
          type="range"
          min={0}
          max={duration || 0}
          step={0.1}
          value={Math.min(currentTime, duration || 0)}
          onChange={handleSeek}
          className="h-1.5 flex-1 accent-brand-navy"
          aria-label="Seek narration"
        />
        <span className="w-9 shrink-0 text-xs tabular-nums text-neutral-400">{formatTime(duration)}</span>

        <select
          value={playbackRate}
          onChange={handleRateChange}
          aria-label="Playback speed"
          className="shrink-0 rounded border border-neutral-300 bg-white px-1 py-1 text-xs text-neutral-700"
        >
          {PLAYBACK_RATES.map((rate) => (
            <option key={rate} value={rate}>
              {rate}x
            </option>
          ))}
        </select>

        {bothAvailable && (
          <div className="flex shrink-0 overflow-hidden rounded border border-neutral-300 text-xs">
            {(['en', 'ne'] as NarrationLanguage[]).map((lang) => (
              <button
                key={lang}
                type="button"
                onClick={() => handleToggleLanguage(lang)}
                className={`px-2 py-1 font-medium transition ${
                  selectedLanguage === lang
                    ? 'bg-brand-navy text-white'
                    : 'bg-white text-neutral-600 hover:bg-neutral-100'
                }`}
              >
                {lang.toUpperCase()}
              </button>
            ))}
          </div>
        )}

        <button
          type="button"
          onClick={() => setShowTranscript((v) => !v)}
          aria-label={showTranscript ? 'Hide transcript' : 'Show transcript'}
          title="Transcript"
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded transition ${
            showTranscript ? 'bg-brand-navy/10 text-brand-navy' : 'text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700'
          }`}
        >
          <FileText className="h-4 w-4" />
        </button>
      </div>

      {isFallback && (
        <p className="mt-1 text-xs text-neutral-500">
          Not yet available in {LANGUAGE_LABEL[preferredLanguage]} — playing {LANGUAGE_LABEL[selectedLanguage]}.
        </p>
      )}
    </div>
  )
}
