import type { SlideTemplate } from '../../types/slides'

interface TemplatePickerProps {
  templates: SlideTemplate[]
  value: number | null
  onChange: (templateId: number | null) => void
  // Shown as a first, distinct option representing "no explicit choice" —
  // used for a per-slide override, where None means "inherit the course's
  // current template" rather than any specific preset.
  allowNone?: boolean
  noneLabel?: string
}

const SWATCH_BUTTON_CLASS =
  'flex flex-col items-center gap-1 rounded-md border p-1.5 text-center transition'

function swatchButtonClass(isSelected: boolean): string {
  return `${SWATCH_BUTTON_CLASS} ${
    isSelected ? 'border-brand-navy ring-1 ring-brand-navy' : 'border-neutral-200 hover:border-neutral-300'
  }`
}

export function TemplatePicker({ templates, value, onChange, allowNone, noneLabel = 'None' }: TemplatePickerProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {allowNone && (
        <button
          type="button"
          onClick={() => onChange(null)}
          aria-pressed={value === null}
          title={noneLabel}
          className={swatchButtonClass(value === null)}
        >
          <div className="flex h-10 w-16 items-center justify-center rounded border border-dashed border-neutral-300 bg-neutral-50 text-[10px] text-neutral-400">
            None
          </div>
          <span className="max-w-16 truncate text-[11px] text-neutral-600">{noneLabel}</span>
        </button>
      )}
      {templates.map((template) => (
        <button
          key={template.id}
          type="button"
          onClick={() => onChange(template.id)}
          aria-pressed={value === template.id}
          title={template.name}
          className={swatchButtonClass(value === template.id)}
        >
          <div className="h-10 w-16 rounded" style={{ background: template.background_css }}>
            <div className="flex h-full flex-col items-start justify-center gap-1 px-2">
              <span className="h-1 w-6 rounded-full" style={{ backgroundColor: template.accent_color }} />
              <span className="h-1 w-8 rounded-full" style={{ backgroundColor: template.text_color }} />
            </div>
          </div>
          <span className="max-w-16 truncate text-[11px] text-neutral-600">{template.name}</span>
        </button>
      ))}
    </div>
  )
}
