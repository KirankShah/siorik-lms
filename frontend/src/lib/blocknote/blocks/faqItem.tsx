import { createReactBlockSpec } from '@blocknote/react'
import { ToggleWrapper } from '../toggleWrapper'

// Same collapsible mechanism as accordionItem, but a distinct block type
// (`faqItem` vs `accordionItem`) so the two are told apart in content_json
// and can be styled/queried independently, per the brief. The block's inline
// content is the question; nested children are the answer.
export const faqItemBlock = createReactBlockSpec(
  {
    type: 'faqItem',
    propSchema: {},
    content: 'inline',
  },
  {
    render: ({ contentRef }) => (
      <div className="w-full rounded-md border border-indigo-100 bg-indigo-50/40 px-2 py-1">
        <ToggleWrapper
          defaultOpen={false}
          accentClassName="text-indigo-400"
          header={
            <div className="flex items-start gap-2">
              <span
                className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-600"
                contentEditable={false}
              >
                Q
              </span>
              <div ref={contentRef} className="font-medium text-indigo-950" />
            </div>
          }
        />
      </div>
    ),
  },
)
