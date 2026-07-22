import { createReactBlockSpec } from '@blocknote/react'
import { ToggleWrapper } from '../toggleWrapper'

// One expandable section. The block's own inline content is the section
// title; nested child blocks (added the normal BlockNote way — Enter then
// Tab) form the expandable body. Several of these in a row form "an
// accordion" — see PageEditor's page comment for why there's no separate
// wrapping container block.
export const accordionItemBlock = createReactBlockSpec(
  {
    type: 'accordionItem',
    propSchema: {},
    content: 'inline',
  },
  {
    render: ({ contentRef }) => (
      <div className="w-full rounded-md border border-slate-200 bg-white px-2 py-1">
        <ToggleWrapper
          defaultOpen
          header={<div ref={contentRef} className="font-medium text-slate-800" />}
        />
      </div>
    ),
  },
)
