import { useEffect, useRef, useState } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { Badge } from '../../components/ui/Badge'
import { Banner } from '../../components/ui/Banner'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { fetchCertificateTemplates, updateCertificateTemplate } from '../../lib/certificatesApi'
import type {
  CertificateTemplate,
  CertificateTemplateFieldName,
  CertificateTemplateInput,
  TextAlign,
} from '../../types/certificates'

const FIELD_LABELS: Record<CertificateTemplateFieldName, string> = {
  staff_name: 'Staff name',
  course_name: 'Course name',
  issue_date: 'Issue date',
}

const PREVIEW_SAMPLE_TEXT: Record<CertificateTemplateFieldName, string> = {
  staff_name: 'Jane Learner',
  course_name: 'Sample Course Title',
  issue_date: 'August 06, 2026',
}

const MARKER_COLORS: Record<CertificateTemplateFieldName | 'qr_code', string> = {
  staff_name: '#2563eb',
  course_name: '#16a34a',
  issue_date: '#db2777',
  qr_code: '#7c3aed',
}

type ActiveTarget = CertificateTemplateFieldName | 'qr_code'

const ALIGN_TO_TRANSFORM: Record<TextAlign, string> = {
  LEFT: 'translate(0, -50%)',
  CENTER: 'translate(-50%, -50%)',
  RIGHT: 'translate(-100%, -50%)',
}

function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, Math.round(value * 100) / 100))
}

// A local editable copy of the position/style fields — clicking the image or
// editing the form only updates this draft; nothing is sent until "Save".
interface Draft {
  staff_name_x_percent: number
  staff_name_y_percent: number
  staff_name_font_size: number
  staff_name_color: string
  staff_name_text_align: TextAlign
  course_name_x_percent: number
  course_name_y_percent: number
  course_name_font_size: number
  course_name_color: string
  course_name_text_align: TextAlign
  issue_date_x_percent: number
  issue_date_y_percent: number
  issue_date_font_size: number
  issue_date_color: string
  issue_date_text_align: TextAlign
  qr_code_x_percent: number
  qr_code_y_percent: number
  qr_code_size_percent: number
}

function draftFromTemplate(template: CertificateTemplate): Draft {
  return {
    staff_name_x_percent: template.staff_name_x_percent,
    staff_name_y_percent: template.staff_name_y_percent,
    staff_name_font_size: template.staff_name_font_size,
    staff_name_color: template.staff_name_color,
    staff_name_text_align: template.staff_name_text_align,
    course_name_x_percent: template.course_name_x_percent,
    course_name_y_percent: template.course_name_y_percent,
    course_name_font_size: template.course_name_font_size,
    course_name_color: template.course_name_color,
    course_name_text_align: template.course_name_text_align,
    issue_date_x_percent: template.issue_date_x_percent,
    issue_date_y_percent: template.issue_date_y_percent,
    issue_date_font_size: template.issue_date_font_size,
    issue_date_color: template.issue_date_color,
    issue_date_text_align: template.issue_date_text_align,
    qr_code_x_percent: template.qr_code_x_percent,
    qr_code_y_percent: template.qr_code_y_percent,
    qr_code_size_percent: template.qr_code_size_percent,
  }
}

export function CertificateTemplatesPage() {
  const [templates, setTemplates] = useState<CertificateTemplate[] | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [activeTarget, setActiveTarget] = useState<ActiveTarget>('staff_name')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [naturalWidth, setNaturalWidth] = useState<number | null>(null)
  const [containerWidth, setContainerWidth] = useState<number | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Scales a field's font_size (defined in px at the background image's own
  // native resolution) down to the size it should render at in this preview,
  // given the image is currently displayed narrower than its natural width.
  const previewScale = naturalWidth && containerWidth ? containerWidth / naturalWidth : null

  useEffect(() => {
    function handleResize() {
      if (containerRef.current) setContainerWidth(containerRef.current.getBoundingClientRect().width)
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  useEffect(() => {
    fetchCertificateTemplates()
      .then((list) => {
        setTemplates(list)
        const defaultTemplate = list.find((t) => t.is_default) ?? list[0]
        if (defaultTemplate) {
          setSelectedId(defaultTemplate.id)
          setDraft(draftFromTemplate(defaultTemplate))
        }
      })
      .catch(() => setError('Could not load certificate templates.'))
  }, [])

  const selectedTemplate = templates?.find((t) => t.id === selectedId) ?? null

  function handleSelectTemplate(id: number) {
    const template = templates?.find((t) => t.id === id)
    if (!template) return
    setSelectedId(id)
    setDraft(draftFromTemplate(template))
    setSuccess(false)
    setError(null)
  }

  function handleImageClick(e: ReactMouseEvent) {
    if (!draft) return
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return
    const x = clampPercent(((e.clientX - rect.left) / rect.width) * 100)
    const y = clampPercent(((e.clientY - rect.top) / rect.height) * 100)
    setDraft({ ...draft, [`${activeTarget}_x_percent`]: x, [`${activeTarget}_y_percent`]: y })
    setSuccess(false)
  }

  async function handleSave() {
    if (!selectedTemplate || !draft) return
    setIsSaving(true)
    setError(null)
    setSuccess(false)
    try {
      const updated = await updateCertificateTemplate(selectedTemplate.id, draft as CertificateTemplateInput)
      setTemplates((prev) => prev?.map((t) => (t.id === updated.id ? updated : t)) ?? null)
      setSuccess(true)
    } catch {
      setError('Could not save calibration changes.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-neutral-900">Certificate template calibration</h1>
        {templates && templates.length > 1 && (
          <select
            className="rounded-md border border-neutral-300 px-3 py-2 text-sm"
            value={selectedId ?? ''}
            onChange={(e) => handleSelectTemplate(Number(e.target.value))}
          >
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
                {t.is_default ? ' (default)' : ''}
              </option>
            ))}
          </select>
        )}
      </div>
      <p className="mt-1 text-sm text-neutral-500">
        Select which field you're placing below, then click on the certificate image to set its position. Position is
        stored as a percentage of the image's own dimensions, so it stays aligned at any resolution.
      </p>

      {error && (
        <Banner variant="warning" className="mt-4">
          {error}
        </Banner>
      )}
      {success && (
        <Banner variant="success" className="mt-4">
          Saved.
        </Banner>
      )}

      {!templates && !error && <p className="mt-6 text-sm text-neutral-400">Loading…</p>}
      {templates && templates.length === 0 && (
        <p className="mt-6 text-sm text-neutral-400">No certificate templates exist yet.</p>
      )}

      {selectedTemplate && draft && (
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="p-4">
            <div
              ref={containerRef}
              onClick={handleImageClick}
              className="relative inline-block w-full max-w-3xl cursor-crosshair select-none"
            >
              <img
                src={selectedTemplate.background_image}
                alt={selectedTemplate.name}
                className="block w-full rounded border border-neutral-200"
                draggable={false}
                onLoad={(e) => {
                  setNaturalWidth(e.currentTarget.naturalWidth)
                  setContainerWidth(containerRef.current?.getBoundingClientRect().width ?? null)
                }}
              />

              {(['staff_name', 'course_name', 'issue_date'] as CertificateTemplateFieldName[]).map((field) => (
                <div
                  key={field}
                  className="pointer-events-none absolute font-serif whitespace-nowrap"
                  style={{
                    left: `${draft[`${field}_x_percent`]}%`,
                    top: `${draft[`${field}_y_percent`]}%`,
                    transform: ALIGN_TO_TRANSFORM[draft[`${field}_text_align`]],
                    color: draft[`${field}_color`],
                    fontSize: previewScale ? `${draft[`${field}_font_size`] * previewScale}px` : '12px',
                  }}
                >
                  {PREVIEW_SAMPLE_TEXT[field]}
                </div>
              ))}

              {(['staff_name', 'course_name', 'issue_date', 'qr_code'] as ActiveTarget[]).map((target) => (
                <div
                  key={target}
                  className={`absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow ${
                    activeTarget === target ? 'ring-2 ring-offset-1' : ''
                  }`}
                  style={{
                    left: `${draft[`${target}_x_percent`]}%`,
                    top: `${draft[`${target}_y_percent`]}%`,
                    background: MARKER_COLORS[target],
                  }}
                  title={target === 'qr_code' ? 'QR code' : FIELD_LABELS[target]}
                />
              ))}

              {draft.qr_code_size_percent > 0 && (
                <div
                  className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 border-2 border-dashed"
                  style={{
                    left: `${draft.qr_code_x_percent}%`,
                    top: `${draft.qr_code_y_percent}%`,
                    width: `${draft.qr_code_size_percent}%`,
                    height: `${draft.qr_code_size_percent}%`,
                    transform: 'translate(0, 0)',
                    borderColor: MARKER_COLORS.qr_code,
                  }}
                />
              )}
            </div>
            <p className="mt-2 text-xs text-neutral-400">
              Preview text is an approximation for calibration only — generate a real certificate to see the exact
              rendered output.
            </p>
          </Card>

          <div className="space-y-4">
            <Card className="p-4">
              <p className="text-xs font-semibold tracking-wide text-neutral-500 uppercase">Field to place</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {(['staff_name', 'course_name', 'issue_date', 'qr_code'] as ActiveTarget[]).map((target) => (
                  <button
                    key={target}
                    type="button"
                    onClick={() => setActiveTarget(target)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                      activeTarget === target
                        ? 'bg-brand-navy text-white'
                        : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
                    }`}
                  >
                    {target === 'qr_code' ? 'QR code' : FIELD_LABELS[target]}
                  </button>
                ))}
              </div>
            </Card>

            {activeTarget === 'qr_code' ? (
              <Card className="p-4">
                <h2 className="text-sm font-semibold text-neutral-900">QR code</h2>
                <div className="mt-3 space-y-3">
                  <Input
                    id="qr-x"
                    label="X position (%)"
                    type="number"
                    step="0.1"
                    value={draft.qr_code_x_percent}
                    onChange={(e) => setDraft({ ...draft, qr_code_x_percent: Number(e.target.value) })}
                  />
                  <Input
                    id="qr-y"
                    label="Y position (%)"
                    type="number"
                    step="0.1"
                    value={draft.qr_code_y_percent}
                    onChange={(e) => setDraft({ ...draft, qr_code_y_percent: Number(e.target.value) })}
                  />
                  <Input
                    id="qr-size"
                    label="Size (% of image width)"
                    type="number"
                    step="0.1"
                    value={draft.qr_code_size_percent}
                    onChange={(e) => setDraft({ ...draft, qr_code_size_percent: Number(e.target.value) })}
                  />
                </div>
              </Card>
            ) : (
              <Card className="p-4">
                <h2 className="text-sm font-semibold text-neutral-900">{FIELD_LABELS[activeTarget]}</h2>
                {activeTarget !== 'staff_name' && !selectedTemplate[`${activeTarget}_font_file`] && (
                  <Badge variant="gold" className="mt-2">
                    Placeholder font
                  </Badge>
                )}
                <div className="mt-3 space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <Input
                      id={`${activeTarget}-x`}
                      label="X (%)"
                      type="number"
                      step="0.1"
                      value={draft[`${activeTarget}_x_percent`]}
                      onChange={(e) => setDraft({ ...draft, [`${activeTarget}_x_percent`]: Number(e.target.value) })}
                    />
                    <Input
                      id={`${activeTarget}-y`}
                      label="Y (%)"
                      type="number"
                      step="0.1"
                      value={draft[`${activeTarget}_y_percent`]}
                      onChange={(e) => setDraft({ ...draft, [`${activeTarget}_y_percent`]: Number(e.target.value) })}
                    />
                  </div>
                  <Input
                    id={`${activeTarget}-font-size`}
                    label="Font size (px, at native image resolution)"
                    type="number"
                    value={draft[`${activeTarget}_font_size`]}
                    onChange={(e) => setDraft({ ...draft, [`${activeTarget}_font_size`]: Number(e.target.value) })}
                  />
                  <div>
                    <label htmlFor={`${activeTarget}-color`} className="block text-sm font-medium text-neutral-700">
                      Color
                    </label>
                    <div className="mt-1 flex items-center gap-2">
                      <input
                        id={`${activeTarget}-color`}
                        type="color"
                        value={draft[`${activeTarget}_color`]}
                        onChange={(e) => setDraft({ ...draft, [`${activeTarget}_color`]: e.target.value })}
                        className="h-9 w-12 rounded border border-neutral-300"
                      />
                      <span className="text-sm text-neutral-500">{draft[`${activeTarget}_color`]}</span>
                    </div>
                  </div>
                  <div>
                    <label htmlFor={`${activeTarget}-align`} className="block text-sm font-medium text-neutral-700">
                      Text align
                    </label>
                    <select
                      id={`${activeTarget}-align`}
                      value={draft[`${activeTarget}_text_align`]}
                      onChange={(e) =>
                        setDraft({ ...draft, [`${activeTarget}_text_align`]: e.target.value as TextAlign })
                      }
                      className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm"
                    >
                      <option value="LEFT">Left</option>
                      <option value="CENTER">Center</option>
                      <option value="RIGHT">Right</option>
                    </select>
                  </div>
                </div>
              </Card>
            )}

            <Button onClick={() => void handleSave()} disabled={isSaving} className="w-full">
              {isSaving ? 'Saving…' : 'Save changes'}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
