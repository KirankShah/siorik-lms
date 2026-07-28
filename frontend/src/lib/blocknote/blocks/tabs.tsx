import { useEffect, useState } from 'react'
import { createReactBlockSpec } from '@blocknote/react'
import type { ReactCustomBlockRenderProps } from '@blocknote/react'
import type { BlockNoteEditorType } from '../editorType'
import '../collapsible.css'

const tabPanelConfig = {
  type: 'tabPanel',
  propSchema: {
    label: { default: 'Tab' },
    isActive: { default: false },
  },
  content: 'none',
} as const

// tabPanel's own children (nested one level deeper) are its rich body.
// `isActive` is a real, persisted prop rather than local component state —
// so the active tab survives a reload and shows correctly in the read-only
// preview pane, which only ever sees content_json (see PageEditor.tsx).
export const tabPanelBlock = createReactBlockSpec(tabPanelConfig, {
  render: ({ block }: ReactCustomBlockRenderProps<typeof tabPanelConfig>) => (
    <div
      className="lms-toggle-wrapper w-full text-xs text-slate-400 italic"
      data-show-children={block.props.isActive ? 'true' : 'false'}
    >
      {block.props.isActive ? `Tab: ${block.props.label}` : `Tab: ${block.props.label} (not selected — hidden from readers)`}
    </div>
  ),
})

// BlockNote's block-union types get unwieldy to thread through a container
// that reads/writes sibling blocks of a specific custom type, so this file
// works against this minimal local shape and crosses back over with a
// deliberate cast at each editor.updateBlock/insertBlocks call.
interface TabPanelData {
  id: string
  props: { label: string; isActive: boolean }
}

function tabPanelPartialBlock(label: string, isActive: boolean) {
  return { type: 'tabPanel', props: { label, isActive }, children: [{ type: 'paragraph' }] }
}

const tabsConfig = {
  type: 'tabs',
  propSchema: {},
  content: 'none',
} as const

function TabsBlockRender({ block: initialBlock, editor }: ReactCustomBlockRenderProps<typeof tabsConfig>) {
  // BlockNote types a custom block's `editor` render prop narrowly (only
  // aware of this one block type), which doesn't fit a container that needs
  // to read/update sibling tabPanel children — widen it back out.
  const fullEditor = editor as unknown as BlockNoteEditorType

  // The container's NodeView isn't guaranteed to re-render when a sibling
  // tabPanel's own props change (that's a separate nested node), so re-read
  // the live block on every editor change instead of trusting the snapshot
  // passed in via props.
  const [, forceUpdate] = useState(0)
  useEffect(() => fullEditor.onChange(() => forceUpdate((n) => n + 1)), [fullEditor])
  const block = fullEditor.getBlock(initialBlock.id) ?? initialBlock

  const panels = block.children.filter((child) => child.type === 'tabPanel') as unknown as TabPanelData[]

  function selectTab(activeId: string) {
    editor.transact(() => {
      for (const panel of panels) {
        editor.updateBlock(panel.id, { props: { isActive: panel.id === activeId } } as never)
      }
    })
  }

  function renameTab(id: string, label: string) {
    editor.updateBlock(id, { props: { label } } as never)
  }

  function addTab() {
    editor.transact(() => {
      const lastPanel = panels[panels.length - 1]
      if (lastPanel) {
        editor.insertBlocks([tabPanelPartialBlock(`Tab ${panels.length + 1}`, false) as never], lastPanel.id, 'after')
      } else {
        editor.insertBlocks([tabPanelPartialBlock('Tab 1', true) as never], block.id, 'after')
      }
    })
  }

  function removeTab(id: string) {
    if (panels.length <= 1) return
    const wasActive = panels.find((p) => p.id === id)?.props.isActive
    editor.transact(() => {
      editor.removeBlocks([id])
      if (wasActive) {
        const remaining = panels.filter((p) => p.id !== id)
        if (remaining[0]) editor.updateBlock(remaining[0].id, { props: { isActive: true } } as never)
      }
    })
  }

  return (
    <div className="w-full rounded-lg border border-slate-200">
      <div className="flex flex-wrap items-center gap-1 border-b border-slate-200 bg-slate-50 px-2 py-1.5" contentEditable={false}>
        {panels.map((panel) => (
          <div
            key={panel.id}
            className={`flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium ${
              panel.props.isActive ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:bg-white/60'
            }`}
          >
            {editor.isEditable ? (
              <input
                value={panel.props.label}
                onMouseDown={() => selectTab(panel.id)}
                onChange={(e) => renameTab(panel.id, e.target.value)}
                className="w-20 bg-transparent focus:outline-none"
              />
            ) : (
              <button type="button" onClick={() => selectTab(panel.id)}>
                {panel.props.label}
              </button>
            )}
            {editor.isEditable && panels.length > 1 && (
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => removeTab(panel.id)}
                className="text-slate-300 hover:text-red-500"
                aria-label="Remove tab"
              >
                ×
              </button>
            )}
          </div>
        ))}
        {editor.isEditable && (
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={addTab}
            className="rounded-md px-2 py-1 text-xs font-medium text-slate-400 hover:bg-white/60 hover:text-slate-700"
          >
            + Tab
          </button>
        )}
      </div>
    </div>
  )
}

// Container whose children must all be tabPanel blocks. Renders the tab
// strip (label inputs + add/remove); switching tabs sets exactly one
// child's `isActive` at a time via editor.updateBlock.
export const tabsBlock = createReactBlockSpec(tabsConfig, { render: TabsBlockRender })
