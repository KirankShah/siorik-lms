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
  return value != null && Number(value) >= 70 ? 'text-emerald-700' : 'text-amber-600'
}

function ordinal(rank: number): string {
  const lastTwoDigits = rank % 100
  const suffix = lastTwoDigits >= 11 && lastTwoDigits <= 13
    ? 'th'
    : ({ 1: 'st', 2: 'nd', 3: 'rd' }[rank % 10] ?? 'th')
  return `${rank}${suffix}`
}

function Rank({ rank }: { rank: number }) {
  if (rank <= 3) {
    const colors = ['text-brand-gold', 'text-slate-500', 'text-amber-700']
    return (
      <span className="inline-flex items-center gap-1.5 font-semibold text-neutral-700">
        <Medal className={`h-4 w-4 ${colors[rank - 1]}`} />
        {rank}
      </span>
    )
  }
  return <span className="font-semibold text-neutral-700">{rank}</span>
}

function quizProgress(entry: LeaderboardEntry): string {
  return `${entry.quizzes_completed} of ${entry.quizzes_required} quizzes`
}

function quizCoverageIncomplete(entry: LeaderboardEntry): boolean {
  return entry.quizzes_required === 0 || entry.quizzes_completed < entry.quizzes_required
}

export function LeaderboardWidget({ entries }: LeaderboardWidgetProps) {
  const { user } = useAuth()
  const rankedEntries = entries?.filter((entry) => entry.knowledge_score != null) ?? []
  const inProgressEntries = entries?.filter((entry) => entry.knowledge_score == null) ?? []
  const myEntry = entries?.find((entry) => entry.user_id === user?.id) ?? null
  const myRankIndex = rankedEntries.findIndex((entry) => entry.user_id === user?.id)
  const myRank = myRankIndex >= 0 ? myRankIndex + 1 : null
  // A learner can hold a Level Assessment result without a Knowledge Score
  // (no course quiz yet), so "assessed" is keyed off the level result alone.
  const hasLevelResult = myEntry?.last_assessed_at != null
  const noScoreLabel = user?.role === 'LEARNER' ? 'Not yet assessed' : 'No learner score'
  const cardState = entries === null ? 'Loading…' : noScoreLabel
  const quizzesRemaining = myEntry ? Math.max(myEntry.quizzes_required - myEntry.quizzes_completed, 0) : 0
  const myQuizCoverageIncomplete = myEntry != null && quizCoverageIncomplete(myEntry)
  const rankState = myQuizCoverageIncomplete
    ? `Not ranked yet · ${quizzesRemaining} ${quizzesRemaining === 1 ? 'quiz' : 'quizzes'} remaining`
    : hasLevelResult ? 'Not ranked yet' : cardState
  const knowledgeState = myQuizCoverageIncomplete
    ? `In progress (${quizProgress(myEntry)})`
    : hasLevelResult ? 'Complete all course quizzes' : cardState
  const topEntries = rankedEntries.slice(0, TOP_RANKS_LIMIT)
  const displayedEntries = [...topEntries, ...inProgressEntries]
  const showOwnPosition = myEntry?.knowledge_score != null && myRank !== null && myRank > TOP_RANKS_LIMIT

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-neutral-900">Leaderboard</h2>
        <p className="mt-1 text-sm text-neutral-500">Ranked by the latest Level Assessment and course quiz results.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="flex items-center gap-4 p-5">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-gold/15">
            <Trophy className="h-6 w-6 text-brand-gold" />
          </span>
          <div>
            <p className="text-sm text-neutral-500">My Rank</p>
            <p className="text-2xl font-semibold text-brand-navy">{myRank === null ? rankState : myRank}</p>
          </div>
        </Card>
        <Card className="flex items-center gap-4 p-5">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-navy/5">
            <BarChart3 className="h-6 w-6 text-brand-navy" />
          </span>
          <div>
            <p className="text-sm text-neutral-500">Current Knowledge</p>
            <p className="text-2xl font-semibold text-brand-navy">
              {myEntry?.knowledge_score == null ? knowledgeState : formatPercent(myEntry.knowledge_score)}
            </p>
          </div>
        </Card>
        <Card className="flex items-center gap-4 p-5">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-navy/5">
            <CalendarDays className="h-6 w-6 text-brand-navy" />
          </span>
          <div>
            <p className="text-sm text-neutral-500">Last Assessed</p>
            <p className="text-xl font-semibold text-brand-navy">
              {hasLevelResult ? formatAssessmentDate(myEntry?.last_assessed_at) : cardState}
            </p>
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden p-0">
        {!entries ? (
          <p className="p-6 text-sm text-neutral-500">Loading…</p>
        ) : displayedEntries.length === 0 ? (
          <p className="p-6 text-sm text-neutral-500">
            Complete a course quiz and a Level Assessment to join the leaderboard.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] border-collapse">
              <thead className="bg-neutral-50">
                <tr className="border-b border-neutral-200 text-left text-xs font-semibold text-neutral-600">
                  <th className="w-20 px-5 py-4">Rank</th>
                  <th className="px-4 py-4">Staff Member</th>
                  <th className="px-4 py-4">Level</th>
                  <th className="px-4 py-4 text-center">Course Quiz Avg.</th>
                  <th className="px-4 py-4 text-center">Latest Level Assessment</th>
                  <th className="bg-brand-navy/5 px-4 py-4 text-center text-brand-navy">Knowledge Score</th>
                  <th className="px-4 py-4">Last Assessed</th>
                </tr>
              </thead>
              <tbody>
                {displayedEntries.map((entry, index) => {
                  const isMe = entry.user_id === user?.id
                  const isRanked = entry.knowledge_score != null
                  const isQuizIncomplete = quizCoverageIncomplete(entry)
                  return (
                    <tr
                      key={entry.user_id}
                      className={`border-b border-neutral-100 last:border-b-0 ${isMe ? 'bg-brand-gold/10' : 'hover:bg-neutral-50'}`}
                    >
                      <td className="px-5 py-4">
                        {isRanked ? <Rank rank={index + 1} /> : <span className="text-neutral-500">—</span>}
                      </td>
                      <td className="px-4 py-4 text-sm font-medium text-neutral-900">
                        {entry.first_name} {entry.last_name}
                        {isMe && <span className="ml-1 text-xs font-normal text-brand-navy">(You)</span>}
                      </td>
                      <td className="px-4 py-4 text-sm text-neutral-600">{entry.assessment_level_display}</td>
                      <td className="px-4 py-4 text-center text-sm text-neutral-700">
                        {isQuizIncomplete ? quizProgress(entry) : formatPercent(entry.current_course_quiz_average)}
                      </td>
                      <td className="px-4 py-4 text-center text-sm text-neutral-700">
                        {formatPercent(entry.latest_level_assessment_score)}
                      </td>
                      <td className={`bg-brand-navy/[0.025] px-4 py-4 text-center text-xl font-bold ${knowledgeColor(entry.knowledge_score)}`}>
                        {isRanked
                          ? formatPercent(entry.knowledge_score)
                          : isQuizIncomplete ? `In progress (${quizProgress(entry)})` : 'Not yet assessed'}
                      </td>
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
        <Card className="space-y-3 border-brand-gold/50 bg-brand-gold/5 p-5">
          <p className="text-sm font-semibold text-brand-navy">Your position: {ordinal(myRank)}</p>
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <p className="text-xs text-neutral-500">Staff Member</p>
              <p className="font-medium text-neutral-900">{myEntry.first_name} {myEntry.last_name}</p>
            </div>
            <div>
              <p className="text-xs text-neutral-500">Level</p>
              <p className="text-neutral-700">{myEntry.assessment_level_display}</p>
            </div>
            <div>
              <p className="text-xs text-neutral-500">Knowledge Score</p>
              <p className={`font-semibold ${knowledgeColor(myEntry.knowledge_score)}`}>
                {formatPercent(myEntry.knowledge_score)}
              </p>
            </div>
            <div>
              <p className="text-xs text-neutral-500">Last Assessed</p>
              <p className="text-neutral-700">{formatAssessmentDate(myEntry.last_assessed_at)}</p>
            </div>
          </div>
        </Card>
      )}

      <div className="flex gap-3 rounded-xl bg-brand-navy/5 p-4 text-sm text-neutral-600 ring-1 ring-brand-navy/10">
        <Info className="mt-0.5 h-5 w-5 shrink-0 text-brand-navy" />
        <div>
          <p className="font-semibold text-brand-navy">
            Knowledge Score = 40% Course Quiz Average + 60% Latest Level Assessment
          </p>
          <p className="mt-1">Certificates remain valid after issue. A new assessment updates only the leaderboard score.</p>
        </div>
      </div>
    </section>
  )
}
