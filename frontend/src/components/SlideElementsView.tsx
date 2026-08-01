import { ElementPreview } from './ElementPreview'
import { findDockedElement, resolveEffectiveLayout } from '../lib/slideLayout'
import type { Layout, SlideElement, SlideTemplate } from '../types/slides'

interface SlideElementsViewProps {
  elements: SlideElement[]
  layout: Layout
  // Null means no template applies to this slide (course has none set and
  // no per-slide override) — renders exactly as it did before templates
  // existed, with no background box and no color overrides.
  template?: SlideTemplate | null
  // Only the learner player passes this — the admin preview already shows
  // the slide's title in its own card header, so it omits this prop rather
  // than rendering it twice.
  title?: string
}

// Shared multi-element layout + template renderer — sits on top of
// ElementPreview (which only knows how to render one element) and decides
// how a slide's elements are arranged and colored as a group. Used by both
// the learner-facing player (ContentSlidePlayer, standard + fullscreen) and
// the admin preview (SlideCard) so a slide's chosen layout and template
// always look identical in both places, the same way ElementPreview already
// keeps single-element rendering identical everywhere.
export function SlideElementsView({ elements, layout, template = null, title }: SlideElementsViewProps) {
  const effectiveLayout = resolveEffectiveLayout(layout, elements)
  const textColor = template?.text_color
  const accentColor = template?.accent_color
  // STACKED reads best capped to a comfortable line length, centered so the
  // margin is symmetric on both sides. The two-column layouts use the full
  // available width instead, since the image column already gives the text
  // column a natural, narrower measure.
  const widthClass = effectiveLayout === 'STACKED' ? 'mx-auto max-w-3xl' : ''

  const heading = title !== undefined && (
    <h1 className={`text-lg font-semibold text-neutral-900 ${widthClass}`} style={{ color: accentColor }}>
      {title}
    </h1>
  )

  const content =
    elements.length === 0 ? (
      <p className={`text-sm text-neutral-400 ${widthClass}`} style={{ color: textColor }}>
        This slide has no content yet.
      </p>
    ) : effectiveLayout === 'STACKED' ? (
      <div className={`space-y-6 ${widthClass}`}>
        {elements.map((element) => (
          <ElementPreview key={element.id} element={element} textColor={textColor} accentColor={accentColor} />
        ))}
      </div>
    ) : (
      (() => {
        const dockedElement = findDockedElement(elements)!
        const restElements = elements.filter((element) => element.id !== dockedElement.id)

        const imageColumn = (
          <div className="w-full shrink-0 sm:w-[40%]">
            <ElementPreview
              element={dockedElement}
              textColor={textColor}
              accentColor={accentColor}
              fill={dockedElement.element_type === 'IMAGE'}
            />
          </div>
        )
        const textColumn = (
          <div className="min-w-0 flex-1 space-y-6">
            {restElements.map((element) => (
              <ElementPreview key={element.id} element={element} textColor={textColor} accentColor={accentColor} />
            ))}
          </div>
        )

        return (
          // items-stretch (flex's own default, made explicit here since the
          // docked IMAGE column now depends on it) is what gives the image
          // column a definite height to resolve its h-full chain against —
          // without it the row's cross-axis size falls back to each column's
          // own content height and the two columns are independently sized.
          <div className="flex flex-col gap-6 sm:flex-row sm:items-stretch">
            {effectiveLayout === 'IMAGE_LEFT' ? (
              <>
                {imageColumn}
                {textColumn}
              </>
            ) : (
              <>
                {textColumn}
                {imageColumn}
              </>
            )}
          </div>
        )
      })()
    )

  if (!template) {
    return (
      <div className="space-y-6">
        {heading}
        {content}
      </div>
    )
  }

  return (
    <div className="space-y-6 rounded-lg p-6" style={{ background: template.background_css }}>
      {heading}
      {content}
    </div>
  )
}
