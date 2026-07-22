import { createReactBlockSpec } from '@blocknote/react'

export type CalloutVariant = 'note' | 'tip' | 'warning' | 'info'

const VARIANTS: Record<CalloutVariant, { label: string; icon: string; className: string }> = {
  note: { label: 'Note', icon: '📝', className: 'border-slate-300 bg-slate-50 text-slate-800' },
  tip: { label: 'Tip', icon: '💡', className: 'border-emerald-300 bg-emerald-50 text-emerald-900' },
  warning: { label: 'Warning', icon: '⚠️', className: 'border-amber-300 bg-amber-50 text-amber-900' },
  info: { label: 'Info', icon: 'ℹ️', className: 'border-blue-300 bg-blue-50 text-blue-900' },
}

const VARIANT_KEYS = Object.keys(VARIANTS) as CalloutVariant[]

export const calloutBlock = createReactBlockSpec(
  {
    type: 'callout',
    propSchema: {
      variant: { default: 'note' as CalloutVariant, values: VARIANT_KEYS },
    },
    content: 'inline',
  },
  {
    render: ({ block, editor, contentRef }) => {
      const variant = VARIANTS[block.props.variant]
      return (
        <div className={`flex gap-3 rounded-lg border p-3 ${variant.className}`}>
          <span className="select-none text-lg leading-6" contentEditable={false}>
            {variant.icon}
          </span>
          <div className="min-w-0 flex-1">
            {editor.isEditable && (
              <div className="mb-1 flex gap-1" contentEditable={false}>
                {VARIANT_KEYS.map((key) => (
                  <button
                    key={key}
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => editor.updateBlock(block, { props: { variant: key } })}
                    className={`rounded px-1.5 py-0.5 text-[10px] font-medium tracking-wide uppercase ${
                      key === block.props.variant ? 'bg-white/80 shadow-sm' : 'opacity-50 hover:opacity-100'
                    }`}
                  >
                    {VARIANTS[key].label}
                  </button>
                ))}
              </div>
            )}
            <div ref={contentRef} />
          </div>
        </div>
      )
    },
  },
)
