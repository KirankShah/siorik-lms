import { createReactBlockSpec } from '@blocknote/react'

type ButtonVariant = 'primary' | 'secondary' | 'outline'

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'bg-slate-900 text-white hover:bg-slate-800',
  secondary: 'bg-slate-100 text-slate-900 hover:bg-slate-200',
  outline: 'border border-slate-300 text-slate-900 hover:bg-slate-50',
}

const VARIANTS = Object.keys(VARIANT_CLASSES) as ButtonVariant[]

export const buttonBlock = createReactBlockSpec(
  {
    type: 'button',
    propSchema: {
      label: { default: 'Click here' },
      url: { default: '' },
      variant: { default: 'primary' as ButtonVariant, values: VARIANTS },
    },
    content: 'none',
  },
  {
    render: ({ block, editor }) => (
      <div className="w-full py-1">
        <a
          href={block.props.url || undefined}
          target="_blank"
          rel="noreferrer"
          contentEditable={false}
          onClick={(e) => {
            // Inside the editor, clicking should let you select the block, not
            // navigate away — the link is only "live" in the read-only preview.
            if (editor.isEditable) e.preventDefault()
          }}
          className={`inline-block rounded-md px-4 py-2 text-sm font-medium transition ${VARIANT_CLASSES[block.props.variant]}`}
        >
          {block.props.label || 'Button'}
        </a>

        {editor.isEditable && (
          <div className="mt-2 flex flex-wrap items-center gap-2" contentEditable={false}>
            <input
              value={block.props.label}
              onChange={(e) => editor.updateBlock(block, { props: { label: e.target.value } })}
              placeholder="Label"
              className="w-32 rounded-md border border-slate-300 px-2 py-1 text-xs"
            />
            <input
              value={block.props.url}
              onChange={(e) => editor.updateBlock(block, { props: { url: e.target.value } })}
              placeholder="https://…"
              className="w-56 rounded-md border border-slate-300 px-2 py-1 text-xs"
            />
            <div className="flex gap-1 rounded-md border border-slate-200 p-0.5">
              {VARIANTS.map((variant) => (
                <button
                  key={variant}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => editor.updateBlock(block, { props: { variant } })}
                  className={`rounded px-2 py-0.5 text-[10px] font-medium capitalize ${
                    block.props.variant === variant ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-100'
                  }`}
                >
                  {variant}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    ),
  },
)
