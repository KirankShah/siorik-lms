import { BarChart3, CalendarDays, Info, Medal, Trophy } from 'lucide-react'
import { Card } from './ui/Card'
import { useAuth } from '../context/AuthContext'
import type { LeaderboardEntry } from '../types/gamification'

interface LeaderboardWidgetProps {
  entries: LeaderboardEntry[] | null
}

const TOP_RANKS_LIMIT = 5

function formatPercent(value: string | null | undefined): string {
  if (value == null || value === '') return '—'
  return `${Number(value).toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1')}%`
}

function formatAssessmentDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(value))
}

function knowledgeColor(value: string | null): string {
  return value != null && Number(value) >= 70 ? 'text-emerald-700' : 'text-amber-700'
}

function ordinal(rank: number): string {
  const lastTwoDigits = rank % 100
  const suffix = lastTwoDigits >= 11 && lastTwoDigits <= 13
    ? 'th'
    : ({ 1: 'st', 2: 'nd', 3: 'rd' }[rank % 10] ?? 'th')
  return `${rank}${suffix}`
}

function initials(entry: LeaderboardEntry): string {
  return `${entry.first_name.charAt(0)}${entry.last_name.charAt(0)}`.toUpperCase()
}

function RankBadge({ rank }: { rank: number }) {
  const styles = [
    'bg-amber-400 text-brand-navy ring-amber-200',
    'bg-slate-300 text-slate-800 ring-slate-200',
    'bg-amber-700 text-white ring-amber-200',
  ]
  if (rank <= 3) {
    return (
      <span className={`inline-flex h-9 w-9 items-center justify-center rounded-full font-bold ring-4 ${styles[rank - 1]}`}>
        {rank}
      </span>
    )
  }
  return <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-brand-navy/8 font-bold text-brand-navy">{rank}</span>
}

function ScoreCell({ value, prominent = false }: { value: string | null; prominent?: boolean }) {
  const numericValue = value == null ? 0 : Math.max(0, Math.min(100, Number(value)))
  return (
    <div className="mx-auto w-28">
      <p className={`text-center font-semibold ${prominent ? `text-lg ${knowledgeColor(value)}` : 'text-sm text-neutral-800'}`}>
        {formatPercent(value)}
      </p>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-neutral-200">
        <div className={`h-full rounded-full ${prominent ? 'bg-brand-gold' : 'bg-brand-navy'}`} style={{ width: `${numericValue}%` }} />
      </div>
    </div>
  )
}

export function LeaderboardWidget({ entries }: LeaderboardWidgetProps) {
  const { user } = useAuth()
  const rankedEntries = entries?.filter((entry) => entry.knowledge_score != null) ?? []
  const myEntry = entries?.find((entry) => entry.user_id === user?.id) ?? null
  const myRankIndex = rankedEntries.findIndex((entry) => entry.user_id === user?.id)
  const myRank = myRankIndex >= 0 ? myRankIndex + 1 : null
  const hasLevelResult = myEntry?.last_assessed_at != null
  const noScoreLabel = user?.role === 'LEARNER' ? 'Not yet assessed' : 'No learner score'
  const cardState = entries === null ? 'Loading…' : noScoreLabel
  const topEntries = rankedEntries.slice(0, TOP_RANKS_LIMIT)
  const showOwnPosition = myEntry?.knowledge_score != null && myRank !== null && myRank > TOP_RANKS_LIMIT

  return (
    <section className="space-y-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-gold/15">
              <Medal className="h-5 w-5 text-amber-600" />
            </span>
            <h2 className="text-2xl font-semibold text-brand-navy">Knowledge Leaderboard</h2>
          </div>
          <p className="mt-2 text-sm text-neutral-500">Top five learners based on assigned path quizzes and the latest Level Assessment.</p>
        </div>
        <span className="w-fit rounded-full bg-brand-navy/5 px-3 py-1 text-xs font-semibold text-brand-navy">Organization-wide standings</span>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="flex items-center gap-4 border-amber-200/70 bg-gradient-to-br from-amber-50 to-white p-5">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-gold/20"><Trophy className="h-6 w-6 text-amber-600" /></span>
          <div className="min-w-0"><p className="text-sm text-neutral-500">My Rank</p><p className="truncate text-2xl font-semibold text-brand-navy">{myRank === null ? cardState : ordinal(myRank)}</p></div>
        </Card>
        <Card className="flex items-center gap-4 p-5">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-navy/5"><BarChart3 className="h-6 w-6 text-brand-navy" /></span>
          <div className="min-w-0"><p className="text-sm text-neutral-500">Current Knowledge</p><p className="truncate text-2xl font-semibold text-brand-navy">{myEntry?.knowledge_score == null ? cardState : formatPercent(myEntry.knowledge_score)}</p></div>
        </Card>
        <Card className="flex items-center gap-4 p-5">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-navy/5"><CalendarDays className="h-6 w-6 text-brand-navy" /></span>
          <div className="min-w-0"><p className="text-sm text-neutral-500">Last Assessed</p><p className="truncate text-xl font-semibold text-brand-navy">{hasLevelResult ? formatAssessmentDate(myEntry?.last_assessed_at) : cardState}</p></div>
        </Card>
      </div>

      <Card className="overflow-hidden border-brand-navy/10 p-0 shadow-sm">
        {!entries ? (
          <p className="p-6 text-sm text-neutral-500">Loading…</p>
        ) : topEntries.length === 0 ? (
          <p className="p-6 text-sm text-neutral-500">Complete a Level Assessment to join the leaderboard. Assigned path quiz questions count automatically.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] border-collapse">
              <thead className="bg-brand-navy">
                <tr className="text-left text-xs font-semibold uppercase tracking-wide text-white/85">
                  <th className="w-20 px-5 py-4">Rank</th><th className="px-4 py-4">Staff Member</th><th className="px-4 py-4">Level</th>
                  <th className="px-4 py-4 text-center">Path Quiz Score</th><th className="px-4 py-4 text-center">Level Assessment</th>
                  <th className="bg-white/5 px-4 py-4 text-center">Overall Score</th><th className="px-4 py-4">Last Assessed</th>
                </tr>
              </thead>
              <tbody>
                {topEntries.map((entry, index) => {
                  const isMe = entry.user_id === user?.id
                  return (
                    <tr key={entry.user_id} className={`border-b border-neutral-100 last:border-b-0 ${isMe ? 'bg-amber-50' : 'hover:bg-neutral-50/80'}`}>
                      <td className="px-5 py-4"><RankBadge rank={index + 1} /></td>
                      <td className="px-4 py-4"><div className="flex items-center gap-3">
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-navy/8 text-xs font-bold text-brand-navy">{initials(entry)}</span>
                        <div><p className="text-sm font-semibold text-neutral-900">{entry.first_name} {entry.last_name}{isMe && <span className="ml-1 text-xs font-normal text-amber-700">(You)</span>}</p><p className="text-xs text-neutral-400">Learner</p></div>
                      </div></td>
                      <td className="px-4 py-4 text-sm text-neutral-600">{entry.assessment_level_display}</td>
                      <td className="px-4 py-4"><ScoreCell value={entry.current_course_quiz_average} /></td>
                      <td className="px-4 py-4"><ScoreCell value={entry.latest_level_assessment_score} /></td>
                      <td className="bg-brand-navy/[0.025] px-4 py-4"><ScoreCell value={entry.knowledge_score} prominent /></td>
                      <td className="px-4 py-4 text-sm text-neutral-600">{formatAssessmentDate(entry.last_assessed_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {showOwnPosition && myEntry && myRank !== null && (
        <Card className="border-brand-gold/50 bg-gradient-to-r from-amber-50 to-white p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div><p className="text-sm font-semibold text-brand-navy">Your position: {ordinal(myRank)}</p><p className="mt-1 text-sm text-neutral-600">{myEntry.first_name} {myEntry.last_name} · {myEntry.assessment_level_display}</p></div>
            <div className="grid grid-cols-3 gap-5 text-center sm:min-w-[430px]">
              <div><p className="text-xs text-neutral-500">Path Quiz</p><p className="font-semibold text-brand-navy">{formatPercent(myEntry.current_course_quiz_average)}</p></div>
              <div><p className="text-xs text-neutral-500">Level Assessment</p><p className="font-semibold text-brand-navy">{formatPercent(myEntry.latest_level_assessment_score)}</p></div>
              <div><p className="text-xs text-neutral-500">Overall</p><p className={`font-bold ${knowledgeColor(myEntry.knowledge_score)}`}>{formatPercent(myEntry.knowledge_score)}</p></div>
            </div>
          </div>
        </Card>
      )}

      <div className="flex gap-3 rounded-xl bg-brand-navy/5 p-4 text-sm text-neutral-600 ring-1 ring-brand-navy/10">
        <Info className="mt-0.5 h-5 w-5 shrink-0 text-brand-navy" />
        <div><p className="font-semibold text-brand-navy">Overall Score = 40% Path Quiz Score + 60% Latest Level Assessment</p><p className="mt-1">The Path Quiz Score uses all question points assigned through the learner's learning path. Unanswered questions count as zero.</p></div>
      </div>
    </section>
  )
}
