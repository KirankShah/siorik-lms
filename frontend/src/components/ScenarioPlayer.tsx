import { useState } from 'react'
import { submitScenarioAttempt } from '../lib/scenariosApi'
import { Button } from './ui/Button'
import { Card } from './ui/Card'
import type { ScenarioChoice, ScenarioNode } from '../types/scenarios'

interface ScenarioPlayerProps {
  slideId: number
  nodes: ScenarioNode[]
  onCompleted: () => void
}

type Stage = { kind: 'prompt' } | { kind: 'feedback'; choice: ScenarioChoice } | { kind: 'ended' }

export function ScenarioPlayer({ slideId, nodes, onCompleted }: ScenarioPlayerProps) {
  const startNode = nodes.find((n) => n.is_start) ?? nodes[0]
  const [currentNodeId, setCurrentNodeId] = useState(startNode.id)
  const [stage, setStage] = useState<Stage>({ kind: 'prompt' })
  const [path, setPath] = useState<number[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const currentNode = nodes.find((n) => n.id === currentNodeId) ?? startNode

  async function handleChoose(choice: ScenarioChoice) {
    const nextPath = [...path, choice.id]
    setPath(nextPath)
    setStage({ kind: 'feedback', choice })

    if (choice.next_node === null) {
      setIsSubmitting(true)
      setError(null)
      try {
        await submitScenarioAttempt({ slide: slideId, path_taken: nextPath })
        onCompleted()
      } catch {
        setError("Couldn't save your progress — you can still finish, but try refreshing if this keeps happening.")
      } finally {
        setIsSubmitting(false)
      }
    }
  }

  function handleContinue(choice: ScenarioChoice) {
    if (choice.next_node === null) {
      setStage({ kind: 'ended' })
      return
    }
    setCurrentNodeId(choice.next_node)
    setStage({ kind: 'prompt' })
  }

  return (
    <Card>
      {stage.kind === 'prompt' && (
        <div>
          {currentNode.prompt_image && (
            <img src={currentNode.prompt_image} alt="" className="mb-3 max-h-64 w-full rounded object-cover" />
          )}
          <div className="text-sm text-neutral-900" dangerouslySetInnerHTML={{ __html: currentNode.prompt }} />
          <div className="mt-4 space-y-2">
            {currentNode.choices.map((choice) => (
              <button
                key={choice.id}
                type="button"
                onClick={() => void handleChoose(choice)}
                className="block w-full rounded-md border border-neutral-200 px-4 py-2.5 text-left text-sm transition hover:border-brand-navy hover:bg-brand-navy/5"
              >
                {choice.choice_text}
              </button>
            ))}
          </div>
        </div>
      )}

      {stage.kind === 'feedback' && (
        <div>
          <p className="text-sm font-medium text-neutral-900">{stage.choice.choice_text}</p>
          {stage.choice.feedback_text && <p className="mt-2 text-sm text-neutral-700">{stage.choice.feedback_text}</p>}
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <Button className="mt-4" disabled={isSubmitting} onClick={() => handleContinue(stage.choice)}>
            {isSubmitting ? 'Saving…' : stage.choice.next_node === null ? 'Finish' : 'Continue'}
          </Button>
        </div>
      )}

      {stage.kind === 'ended' && (
        <div className="text-center">
          <p className="text-base font-semibold text-neutral-900">Scenario complete</p>
          <p className="mt-1 text-sm text-neutral-500">You can move on to the next slide.</p>
        </div>
      )}
    </Card>
  )
}
