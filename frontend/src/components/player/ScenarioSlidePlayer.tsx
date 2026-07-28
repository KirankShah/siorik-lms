import { useEffect, useState } from 'react'
import { ScenarioPlayer } from '../ScenarioPlayer'
import { fetchScenarioNodesForSlide } from '../../lib/scenariosApi'
import type { ScenarioNode } from '../../types/scenarios'
import type { SlideSummary } from '../../types/slides'

interface ScenarioSlidePlayerProps {
  slide: SlideSummary
  onSubmitted: () => void
}

export function ScenarioSlidePlayer({ slide, onSubmitted }: ScenarioSlidePlayerProps) {
  const [nodes, setNodes] = useState<ScenarioNode[] | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setNodes(undefined)
    fetchScenarioNodesForSlide(slide.id)
      .then(setNodes)
      .catch(() => setError('Could not load this scenario.'))
  }, [slide.id])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (nodes === undefined) return <p className="text-sm text-neutral-500">Loading scenario…</p>
  if (nodes.length === 0) return <p className="text-sm text-neutral-400 italic">This scenario hasn't been set up yet.</p>

  // key={slide.id} forces a fresh ScenarioPlayer (and its internal path/stage
  // state) whenever the learner navigates to a different scenario slide.
  return <ScenarioPlayer key={slide.id} slideId={slide.id} nodes={nodes} onCompleted={onSubmitted} />
}
