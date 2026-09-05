import { useEffect, useRef, useState } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { Badge } from '../../components/ui/Badge'
import { Banner } from '../../components/ui/Banner'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { useAuth } from '../../context/AuthContext'
import { fetchOrganizations } from '../../lib/accountsApi'
import {
  createCertificateTemplate,
  fetchCertificateTemplates,
  updateCertificateTemplate,
} from '../../lib/certificatesApi'
import { isPlatformAdminRole } from '../../lib/roles'
import type { Organization } from '../../types/auth'
import type {
  CertificateTemplate,
  CertificateTemplateFieldName,
  CertificateTemplateInput,
  TextAlign,
} from '../../types/certificates'

// The template calibration "slot" the admin is working on — a specific
// organization's own template, or the platform-level one (organization null).
// A PLATFORM_ADMIN can switch between every slot; an ORG_ADMIN/INSTRUCTOR is
// locked to their own organization's slot (see visibleSlots below).
interface TemplateSlot {
  key: string
  label: string
  organizationId: number | null
}

const PLATFORM_SLOT: TemplateSlot = { key: 'platform', label: 'Platform Default', organizationId: null }

function findTemplateForSlot(templates: CertificateTemplate[], slot: TemplateSlot): CertificateTemplate | null {
  if (slot.organizationId === null) {
    return (
      templates.find((t) => t.organization === null && t.is_default) ??
      templates.find((t) => t.organization === null) ??
      null
    )
  }
  return templates.find((t) => t.organization === slot.organizationId) ?? null
}

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
  const { user } = useAuth()
  const isPlatformAdmin = isPlatformAdminRole(user?.role)

  const [organizations, setOrganizations] = useState<Organization[] | null>(null)
  const [templates, setTemplates] = useState<CertificateTemplate[] | null>(null)
  const [selectedSlotKey, setSelectedSlotKey] = useState<string>(PLATFORM_SLOT.key)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [activeTarget, setActiveTarget] = useState<ActiveTarget>('staff_name')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [naturalWidth, setNaturalWidth] = useState<number | null>(null)
  const [containerWidth, setContainerWidth] = useState<number | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Shown instead of the calibration UI when the selected slot has no
  // template yet — an org (or the platform) uploads its own background image
  // to create one before there's anything to calibrate.
  const [newTemplateName, setNewTemplateName] = useState('')
  const [newTemplateFile, setNewTemplateFile] = useState<File | null>(null)
  const [isCreating, setIsCreating] = useState(false)

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

  // Only a PLATFORM_ADMIN can switch organizations — an ORG_ADMIN/INSTRUCTOR
  // is locked to their own org's slot (see `slots` below), so there's no need
  // to fetch the full organization list for them.
  useEffect(() => {
    if (isPlatformAdmin) {
      fetchOrganizations()
        .then(setOrganizations)
        .catch(() => setOrganizations([]))
    }
  }, [isPlatformAdmin])

  useEffect(() => {
    fetchCertificateTemplates()
      .then(setTemplates)
      .catch(() => setError('Could not load certificate templates.'))
  }, [])

  const slots: TemplateSlot[] = isPlatformAdmin
    ? [PLATFORM_SLOT, ...(organizations ?? []).map((org) => ({ key: String(org.id), label: org.name, organizationId: org.id }))]
    : user?.organization
      ? [{ key: String(user.organization.id), label: user.organization.name, organizationId: user.organization.id }]
      : []

  // Falls back to the only slot a non-admin has, without waiting on a
  // separate effect to catch up to `user` loading.
  const selectedSlot = slots.find((slot) => slot.key === selectedSlotKey) ?? slots[0] ?? null
  const selectedTemplate = templates && selectedSlot ? findTemplateForSlot(templates, selectedSlot) : null

  // Populates the draft once the selected slot's template first resolves
  // (initial load, or the fetch completing after a slot switch); handleSave/
  // handleSelectSlot/handleCreate all set it explicitly themselves too.
  useEffect(() => {
    if (selectedTemplate && !draft) {
      setDraft(draftFromTemplate(selectedTemplate))
    }
  }, [selectedTemplate, draft])

  function handleSelectSlot(key: string) {
    setSelectedSlotKey(key)
    setSuccess(false)
    setError(null)
    setNewTemplateName('')
    setNewTemplateFile(null)
    const slot = slots.find((s) => s.key === key)
    const template = templates && slot ? findTemplateForSlot(templates, slot) : null
    setDraft(template ? draftFromTemplate(template) : null)
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

  async function handleCreate() {
    if (!selectedSlot || !newTemplateFile) return
    setIsCreating(true)
    setError(null)
    try {
      const created = await createCertificateTemplate({
        name: newTemplateName.trim() || selectedSlot.label,
        organization: selectedSlot.organizationId,
        background_image: newTemplateFile,
        // This tool only manages one "Platform Default" slot, so a new
        // platform-level template created here is automatically it.
        is_default: selectedSlot.organizationId === null,
      })
      setTemplates((prev) => [...(prev ?? []), created])
      setDraft(draftFromTemplate(created))
      setNewTemplateName('')
      setNewTemplateFile(null)
    } catch {
      setError('Could not create the certificate template.')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-neutral-900">Certificate template calibration</h1>
        {isPlatformAdmin && slots.length > 1 && (
          <select
            className="rounded-md border border-neutral-300 px-3 py-2 text-sm"
            value={selectedSlotKey}
            onChange={(e) => handleSelectSlot(e.target.value)}
          >
            {slots.map((slot) => (
              <option key={slot.key} value={slot.key}>
                {slot.label}
              </option>
            ))}
          </select>
        )}
      </div>
      <p className="mt-1 text-sm text-neutral-500">
        {isPlatformAdmin
          ? "Each organization calibrates its own certificate independently of the platform default — select which one to work on above. "
          : `Calibrating ${selectedSlot?.label ?? 'your organization'}'s own certificate, independent of the platform default. `}
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
      {templates && !selectedSlot && (
        <p className="mt-6 text-sm text-neutral-400">
          You don't belong to an organization, so there's no certificate template for you to manage.
        </p>
      )}

      {templates && selectedSlot && !selectedTemplate && (
        <Card className="mt-6 max-w-md p-4">
          <h2 className="text-sm font-semibold text-neutral-900">No certificate template yet for {selectedSlot.label}</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Upload {selectedSlot.organizationId === null ? 'the platform-wide' : "this organization's own"} certificate
            background image — logo, signature, and all — to start calibrating one, independent of{' '}
            {selectedSlot.organizationId === null ? 'any organization template' : 'the platform default'}.
          </p>
          <div className="mt-4 space-y-3">
            <Input
              id="new-template-name"
              label="Template name"
              placeholder={selectedSlot.label}
              value={newTemplateName}
              onChange={(e) => setNewTemplateName(e.target.value)}
            />
            <div>
              <label className="block text-sm font-medium text-neutral-700">Certificate background image</label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setNewTemplateFile(e.target.files?.[0] ?? null)}
                className="mt-1 text-sm"
              />
            </div>
            <Button onClick={() => void handleCreate()} disabled={!newTemplateFile || isCreating}>
              {isCreating ? 'Creating…' : 'Create Template'}
            </Button>
          </div>
        </Card>
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
