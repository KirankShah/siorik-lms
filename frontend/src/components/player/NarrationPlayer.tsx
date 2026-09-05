import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { RefObject } from 'react'
import { FileText, Pause, Play, X } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import type { NarrationLanguage } from '../../types/auth'
import type { SlideNarration } from '../../types/narration'

interface NarrationPlayerProps {
  narrations: SlideNarration[]
  onClose: () => void
  canvasRef: RefObject<HTMLDivElement | null>
}

const LANGUAGE_LABEL: Record<NarrationLanguage, string> = { en: 'English', ne: 'Nepali' }
const PLAYBACK_RATES = [0.75, 1, 1.25, 1.5]

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds)) return '0:00'
  const total = Math.floor(seconds)
  const minutes = Math.floor(total / 60)
  const secs = total % 60
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

// Splits on English/Nepali sentence-ending punctuation (the Devanagari
// danda "।" included) to get karaoke-style highlight units. There's no
// per-word timing from Azure TTS stored anywhere (the backend only saves
// the finished audio_file, not word-boundary events), so which sentence is
// "active" is an estimate — each sentence's time range is its share of
// script_text's total character count, applied to the audio's actual
// duration. That's a reasonable approximation for narration-paced speech,
// not an exact sync — a real fix needs Azure's word-boundary events
// captured at generation time and stored alongside the audio.
function splitIntoSentences(text: string): string[] {
  return text
    .split(/(?<=[.!?।])\s+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

// Docked above the mascot button once a learner clicks it: language toggle,
// speed, and audio transport, plus a "Transcript" button that independently
// toggles a separate reading pane (portaled into the slide canvas itself —
// see canvasRef — so "roughly a quarter of the slide" is sized against the
// real slide box in both standard and fullscreen, not the viewport).
// Supplementary aid — never touches SlidePlayer's dwell timer or completion
// gating.
export function NarrationPlayer({ narrations, onClose, canvasRef }: NarrationPlayerProps) {
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
  const sentenceRefs = useRef<(HTMLSpanElement | null)[]>([])

  const activeNarration = narrations.find((n) => n.language === selectedLanguage) ?? narrations[0]
  const isFallback = !bothAvailable && selectedLanguage !== preferredLanguage

  const sentenceRanges = useMemo(() => {
    const sentences = splitIntoSentences(activeNarration.script_text)
    const totalChars = sentences.reduce((sum, s) => sum + s.length, 0) || 1
    let cumulative = 0
    return sentences.map((text) => {
      const start = cumulative / totalChars
      cumulative += text.length
      return { text, start, end: cumulative / totalChars }
    })
  }, [activeNarration.script_text])

  const progress = duration > 0 ? currentTime / duration : 0
  const activeSentenceIndex = sentenceRanges.findIndex((r) => progress >= r.start && progress < r.end)

  useEffect(() => {
    if (!showTranscript || activeSentenceIndex < 0) return
    sentenceRefs.current[activeSentenceIndex]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [showTranscript, activeSentenceIndex])

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

  const transcriptPane = showTranscript && canvasRef.current && (
    <div className="no-print pointer-events-auto absolute inset-y-0 right-0 z-20 flex w-1/4 min-w-[240px] max-w-xs flex-col border-l border-neutral-200 bg-white shadow-2xl">
      <div className="flex shrink-0 items-center justify-between border-b border-neutral-100 px-4 py-3">
        <span className="text-sm font-semibold text-neutral-700">Transcript</span>
        <button
          type="button"
          onClick={() => setShowTranscript(false)}
          aria-label="Close transcript"
          className="text-neutral-400 transition hover:text-neutral-700"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 text-sm leading-relaxed text-neutral-700">
        {isFallback && (
          <p className="mb-3 text-xs text-neutral-500">
            Not yet available in {LANGUAGE_LABEL[preferredLanguage]} — showing {LANGUAGE_LABEL[selectedLanguage]}.
          </p>
        )}
        <p>
          {sentenceRanges.map((sentence, i) => (
            <span
              key={i}
              ref={(el) => {
                sentenceRefs.current[i] = el
              }}
              className={`rounded ${i === activeSentenceIndex ? 'bg-brand-gold/30 text-neutral-900' : ''}`}
            >
              {sentence.text}{' '}
            </span>
          ))}
        </p>
      </div>
    </div>
  )

  return (
    <>
      <div className="absolute right-0 bottom-full mb-4 w-96 max-w-[90vw] rounded-lg border border-neutral-200 bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-neutral-100 px-4 py-3">
          <span className="text-sm font-semibold text-neutral-700">Narration</span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close narration player"
            className="text-neutral-400 transition hover:text-neutral-700"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            {bothAvailable ? (
              <div className="flex overflow-hidden rounded border border-neutral-300 text-xs">
                {(['en', 'ne'] as NarrationLanguage[]).map((lang) => (
                  <button
                    key={lang}
                    type="button"
                    onClick={() => handleToggleLanguage(lang)}
                    className={`px-3 py-1.5 font-medium transition ${
                      selectedLanguage === lang
                        ? 'bg-brand-navy text-white'
                        : 'bg-white text-neutral-600 hover:bg-neutral-100'
                    }`}
                  >
                    {LANGUAGE_LABEL[lang]}
                  </button>
                ))}
              </div>
            ) : (
              <span />
            )}

            <select
              value={playbackRate}
              onChange={handleRateChange}
              aria-label="Playback speed"
              className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-700"
            >
              {PLAYBACK_RATES.map((rate) => (
                <option key={rate} value={rate}>
                  {rate}x
                </option>
              ))}
            </select>
          </div>

          {isFallback && (
            <p className="text-xs text-neutral-500">
              Not yet available in {LANGUAGE_LABEL[preferredLanguage]} — playing {LANGUAGE_LABEL[selectedLanguage]}.
            </p>
          )}

          <div className="flex items-center gap-3 rounded-lg border border-neutral-200 bg-neutral-50 p-3">
            <button
              type="button"
              onClick={togglePlay}
              aria-label={isPlaying ? 'Pause narration' : 'Play narration'}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-navy text-white transition hover:bg-brand-navy-light"
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
          </div>

          <button
            type="button"
            onClick={() => setShowTranscript((v) => !v)}
            className={`flex w-full items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition ${
              showTranscript
                ? 'border-brand-navy bg-brand-navy/5 text-brand-navy'
                : 'border-neutral-300 text-neutral-600 hover:bg-neutral-50'
            }`}
          >
            <FileText className="h-4 w-4" />
            {showTranscript ? 'Hide transcript' : 'Show transcript'}
          </button>
        </div>
      </div>

      {transcriptPane && createPortal(transcriptPane, canvasRef.current!)}
    </>
  )
}
