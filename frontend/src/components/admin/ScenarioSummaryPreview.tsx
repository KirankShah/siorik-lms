import { useEffect, useState } from 'react'
import { GitBranch } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { fetchScenarioNodesForSlide } from '../../lib/scenariosApi'
import type { ScenarioNode } from '../../types/scenarios'

export function ScenarioSummaryPreview({ slideId }: { slideId: number }) {
  const [nodes, setNodes] = useState<ScenarioNode[] | undefined>(undefined)

  useEffect(() => {
    setNodes(undefined)
    fetchScenarioNodesForSlide(slideId)
      .then(setNodes)
      .catch(() => setNodes([]))
  }, [slideId])

  if (nodes === undefined) return <p className="text-sm text-neutral-500">Loading…</p>

  if (nodes.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-neutral-400">
        <GitBranch className="h-4 w-4" />
        No scenario yet — click edit to build one.
      </div>
    )
  }

  const startNode = nodes.find((n) => n.is_start)
  const endingCount = nodes.reduce((count, node) => count + node.choices.filter((c) => c.next_node === null).length, 0)

  return (
    <div>
      {startNode?.prompt ? (
        <div className="line-clamp-2 text-sm text-neutral-700" dangerouslySetInnerHTML={{ __html: startNode.prompt }} />
      ) : (
        <p className="text-sm text-neutral-400">No starting prompt written yet.</p>
      )}
      <div className="mt-1.5 flex flex-wrap gap-2">
        <Badge variant="navy">
          {nodes.length} {nodes.length === 1 ? 'node' : 'nodes'}
        </Badge>
        <Badge>
          {endingCount} {endingCount === 1 ? 'ending' : 'endings'}
        </Badge>
        {!startNode && <Badge variant="gold">No start node set</Badge>}
      </div>
    </div>
  )
}
