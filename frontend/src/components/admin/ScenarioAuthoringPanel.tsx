import { useEffect, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Button } from '../ui/Button'
import { RichTextField } from './RichTextField'
import {
  createScenarioChoice,
  createScenarioNode,
  deleteScenarioChoice,
  deleteScenarioNode,
  fetchScenarioNodesForSlide,
  updateScenarioChoice,
  updateScenarioNode,
} from '../../lib/scenariosApi'
import type { ScenarioChoice, ScenarioNode } from '../../types/scenarios'

// Keeps this a manageable flat list rather than a full graph-editing canvas.
const MAX_NODES = 10
const MIN_CHOICES = 2
const MAX_CHOICES = 4

interface ScenarioAuthoringPanelProps {
  slideId: number
}

export function ScenarioAuthoringPanel({ slideId }: ScenarioAuthoringPanelProps) {
  const [nodes, setNodes] = useState<ScenarioNode[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    fetchScenarioNodesForSlide(slideId)
      .then(setNodes)
      .catch(() => setError('Could not load this scenario.'))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [slideId])

  async function handleAddNode() {
    setError(null)
    try {
      const nodeKey = `node-${(nodes?.length ?? 0) + 1}`
      await createScenarioNode({
        slide: slideId,
        node_key: nodeKey,
        prompt: '',
        is_start: (nodes?.length ?? 0) === 0,
      })
      load()
    } catch {
      setError('Could not add node.')
    }
  }

  if (nodes === null && !error) return <p className="text-sm text-neutral-500">Loading scenario…</p>

  const nodeList = nodes ?? []

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-neutral-900">Scenario</h3>
          <p className="mt-0.5 text-xs text-neutral-400">
            Build a small decision tree — aim for 3-5 decision points to keep this manageable for learners.
          </p>
        </div>
        <Button size="sm" onClick={() => void handleAddNode()} disabled={nodeList.length >= MAX_NODES}>
          <Plus className="h-4 w-4" /> Add node
        </Button>
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      {nodeList.length === 0 ? (
        <div className="rounded-xl border border-dashed border-neutral-300 p-6 text-center">
          <p className="text-sm text-neutral-500">This scenario doesn't have any nodes yet — add one to get started.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {nodeList.map((node) => (
            <NodeEditor key={node.id} node={node} allNodes={nodeList} onChanged={load} />
          ))}
        </div>
      )}
    </div>
  )
}

function NodeEditor({
  node,
  allNodes,
  onChanged,
}: {
  node: ScenarioNode
  allNodes: ScenarioNode[]
  onChanged: () => void
}) {
  const [nodeKey, setNodeKey] = useState(node.node_key)
  const [prompt, setPrompt] = useState(node.prompt)
  const [error, setError] = useState<string | null>(null)
  const [isSavingPrompt, setIsSavingPrompt] = useState(false)

  async function handleSaveKey() {
    if (nodeKey === node.node_key) return
    try {
      await updateScenarioNode(node.id, { node_key: nodeKey })
      onChanged()
    } catch {
      setError('Could not update node key — it must be unique on this slide.')
      setNodeKey(node.node_key)
    }
  }

  async function handleSavePrompt() {
    if (prompt === node.prompt) return
    setIsSavingPrompt(true)
    try {
      await updateScenarioNode(node.id, { prompt })
      onChanged()
    } catch {
      setError('Could not save prompt.')
    } finally {
      setIsSavingPrompt(false)
    }
  }

  async function handleImageChange(file: File) {
    try {
      await updateScenarioNode(node.id, { prompt_image: file })
      onChanged()
    } catch {
      setError('Could not upload image.')
    }
  }

  async function handleSetStart() {
    try {
      await updateScenarioNode(node.id, { is_start: true })
      onChanged()
    } catch {
      setError('Could not set as start node.')
    }
  }

  async function handleDeleteNode() {
    if (!window.confirm('Delete this node and all its choices? Any choice pointing to it will end the scenario instead.')) return
    try {
      await deleteScenarioNode(node.id)
      onChanged()
    } catch {
      setError('Could not delete node.')
    }
  }

  async function handleAddChoice() {
    try {
      await createScenarioChoice({
        node: node.id,
        choice_text: '',
        next_node: null,
        order: node.choices.length + 1,
      })
      onChanged()
    } catch {
      setError('Could not add choice.')
    }
  }

  return (
    <div className={`rounded-lg border p-4 ${node.is_start ? 'border-brand-navy/40 bg-brand-navy/5' : 'border-neutral-200'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <input
            value={nodeKey}
            onChange={(e) => setNodeKey(e.target.value)}
            onBlur={() => void handleSaveKey()}
            className="min-w-0 flex-1 rounded border border-neutral-300 px-2 py-1 text-sm font-medium"
          />
          {node.is_start && (
            <span className="shrink-0 rounded-full bg-brand-navy px-2 py-0.5 text-xs font-medium text-white">Start</span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {!node.is_start && (
            <button type="button" onClick={() => void handleSetStart()} className="text-xs font-medium text-brand-navy hover:underline">
              Set as start
            </button>
          )}
          <button type="button" onClick={() => void handleDeleteNode()} className="text-neutral-300 hover:text-red-500" aria-label="Delete node">
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="mt-3">
        <label className="block text-xs font-medium text-neutral-700">Prompt</label>
        <div className="mt-1">
          <RichTextField
            key={node.id}
            initialHtml={prompt}
            onChange={setPrompt}
            placeholder="What happens at this point in the scenario?"
            minHeight="100px"
          />
        </div>
        <button
          type="button"
          onClick={() => void handleSavePrompt()}
          disabled={isSavingPrompt || prompt === node.prompt}
          className="mt-1 text-xs font-medium text-brand-navy hover:underline disabled:opacity-40"
        >
          {isSavingPrompt ? 'Saving…' : 'Save prompt'}
        </button>
      </div>

      <div className="mt-2 flex items-center gap-3">
        {node.prompt_image ? (
          <img src={node.prompt_image} alt="" className="h-16 w-16 rounded border border-neutral-200 object-cover" />
        ) : (
          <label className="cursor-pointer text-xs text-neutral-400 hover:text-brand-navy">
            + Add image
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && void handleImageChange(e.target.files[0])}
            />
          </label>
        )}
      </div>

      <div className="mt-4 border-t border-neutral-100 pt-3">
        <p className="mb-1.5 text-xs font-medium text-neutral-500">
          Choices ({node.choices.length}/{MAX_CHOICES})
        </p>
        <div className="space-y-2">
          {node.choices.map((choice) => (
            <ChoiceEditor key={choice.id} choice={choice} allNodes={allNodes} onChanged={onChanged} />
          ))}
        </div>
        {node.choices.length < MAX_CHOICES && (
          <button type="button" onClick={() => void handleAddChoice()} className="mt-2 text-xs font-medium text-brand-navy hover:underline">
            + Add choice
          </button>
        )}
        {node.choices.length < MIN_CHOICES && (
          <p className="mt-1 text-xs text-amber-600">Add at least {MIN_CHOICES} choices for this node.</p>
        )}
      </div>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  )
}

function ChoiceEditor({
  choice,
  allNodes,
  onChanged,
}: {
  choice: ScenarioChoice
  allNodes: ScenarioNode[]
  onChanged: () => void
}) {
  const [error, setError] = useState<string | null>(null)

  async function handleTextChange(text: string) {
    try {
      await updateScenarioChoice(choice.id, { choice_text: text })
      onChanged()
    } catch {
      setError('Could not update choice.')
    }
  }

  async function handleFeedbackChange(text: string) {
    try {
      await updateScenarioChoice(choice.id, { feedback_text: text })
      onChanged()
    } catch {
      setError('Could not update feedback.')
    }
  }

  async function handleNextNodeChange(value: string) {
    try {
      await updateScenarioChoice(choice.id, { next_node: value === '' ? null : Number(value) })
      onChanged()
    } catch {
      setError('Could not update destination.')
    }
  }

  async function handleToggleRecommended() {
    try {
      await updateScenarioChoice(choice.id, { is_recommended: !choice.is_recommended })
      onChanged()
    } catch {
      setError('Could not update choice.')
    }
  }

  async function handleRemove() {
    try {
      await deleteScenarioChoice(choice.id)
      onChanged()
    } catch {
      setError('Could not remove choice.')
    }
  }

  return (
    <div className={`rounded-md border p-2 ${choice.is_recommended ? 'border-emerald-300 bg-emerald-50' : 'border-neutral-200'}`}>
      <div className="flex items-center gap-2">
        <input
          defaultValue={choice.choice_text}
          onBlur={(e) => e.target.value !== choice.choice_text && void handleTextChange(e.target.value)}
          placeholder="Choice text"
          className="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
        />
        <select
          defaultValue={choice.next_node ?? ''}
          onChange={(e) => void handleNextNodeChange(e.target.value)}
          className="rounded border border-neutral-300 px-2 py-1 text-sm"
        >
          <option value="">— End scenario —</option>
          {allNodes
            .filter((n) => n.id !== choice.node)
            .map((n) => (
              <option key={n.id} value={n.id}>
                {n.node_key}
              </option>
            ))}
        </select>
        <label className="flex shrink-0 items-center gap-1 text-xs text-neutral-500">
          <input
            type="checkbox"
            checked={choice.is_recommended ?? false}
            onChange={() => void handleToggleRecommended()}
            className="h-3.5 w-3.5"
          />
          Recommended
        </label>
        <button type="button" onClick={() => void handleRemove()} className="text-neutral-300 hover:text-red-500" aria-label="Remove choice">
          ✕
        </button>
      </div>
      <textarea
        defaultValue={choice.feedback_text}
        onBlur={(e) => e.target.value !== choice.feedback_text && void handleFeedbackChange(e.target.value)}
        placeholder="Feedback shown after picking this choice…"
        rows={2}
        className="mt-1.5 w-full rounded border border-neutral-300 px-2 py-1 text-sm"
      />
      {!choice.feedback_text.trim() && (
        <p className="mt-1 flex items-center gap-1.5 text-xs text-red-600">
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-red-500" aria-hidden="true" />
          Missing feedback
        </p>
      )}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}
