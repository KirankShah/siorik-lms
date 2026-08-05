import { useRef } from 'react'
import { ElementPreview } from './ElementPreview'
import { ScrollHint, useScrollOverflow } from './ScrollHint'
import { findDockedElement, resolveEffectiveLayout } from '../lib/slideLayout'
import type { ElementType, ImageColumnWidth, Layout, SlideElement, SlideTemplate } from '../types/slides'

// A STACKED slide whose only element is one of these renders that element
// "dominant" (large, centered) rather than at its normal capped size — see
// CanvasStackedContent. Only meaningful in canvasMode; the admin preview
// never sizes anything this way.
const DOMINANT_ELEMENT_TYPES: ElementType[] = ['IMAGE', 'VIDEO_AUDIO', 'EMBED', 'BREAKOUT_IMAGE']

// Literal, complete class strings (not built from an interpolated number) so
// Tailwind's static scanner can actually find and generate them — a
// template literal like `max-w-[${n}%]` would never get picked up.
const IMAGE_COLUMN_MAX_WIDTH_CLASS: Record<ImageColumnWidth, string> = {
  COMPACT: 'max-w-[35%]',
  STANDARD: 'max-w-[45%]',
  WIDE: 'max-w-[55%]',
}

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
  // Set only by the student-facing player (ContentSlidePlayer), which
  // renders this inside SlideCanvas's fixed 16:9 box. Switches STACKED to a
  // single scrolling-or-centered region and IMAGE_LEFT/IMAGE_RIGHT to a
  // fixed-height row with an edge-to-edge image column plus an
  // independently-scrolling text column. The admin preview (SlideCard)
  // never sets this, so its flexible, flowing card is completely unchanged
  // by anything below.
  canvasMode?: boolean
  // IMAGE_LEFT/IMAGE_RIGHT canvasMode only — per-slide cap on how wide the
  // docked image column can grow (see Slide.image_column_width). Defaults
  // to STANDARD, matching the backend field's own default.
  imageColumnWidth?: ImageColumnWidth
}

// Shared multi-element layout + template renderer — sits on top of
// ElementPreview (which only knows how to render one element) and decides
// how a slide's elements are arranged and colored as a group. Used by both
// the learner-facing player (ContentSlidePlayer, standard + fullscreen) and
// the admin preview (SlideCard) so a slide's chosen layout and template
// always look identical in both places, the same way ElementPreview already
// keeps single-element rendering identical everywhere.
export function SlideElementsView({
  elements,
  layout,
  template = null,
  title,
  canvasMode = false,
  imageColumnWidth = 'STANDARD',
}: SlideElementsViewProps) {
  const effectiveLayout = resolveEffectiveLayout(layout, elements)
  const textColor = template?.text_color
  const accentColor = template?.accent_color

  if (canvasMode) {
    return (
      <CanvasBody
        elements={elements}
        effectiveLayout={effectiveLayout}
        template={template}
        textColor={textColor}
        accentColor={accentColor}
        title={title}
        imageColumnWidth={imageColumnWidth}
      />
    )
  }

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

interface CanvasBodyProps {
  elements: SlideElement[]
  effectiveLayout: Layout
  template: SlideTemplate | null
  textColor?: string
  accentColor?: string
  title?: string
  imageColumnWidth: ImageColumnWidth
}

// canvasMode=true's root: a full-height (fills SlideCanvas exactly) flex
// column of [heading, scrollable-or-split content]. Template background, if
// any, wraps the whole thing so it covers the entire canvas rather than
// just the content's own height, the way the non-canvas p-6 box only ever
// covered its content.
function CanvasBody({ elements, effectiveLayout, template, textColor, accentColor, title, imageColumnWidth }: CanvasBodyProps) {
  // Only fade toward a plain, known color — template.background_css can be
  // an arbitrary CSS `background` value (gradient, image, ...) that can't be
  // reused as a linear-gradient() color stop, so templated slides fall back
  // to the chevron badge alone rather than risk a visibly wrong-colored fade.
  const fadeColor = template ? null : '#ffffff'

  const heading = title !== undefined && (
    <h1 className="shrink-0 px-6 pt-6 pb-2 text-lg font-semibold text-neutral-900" style={{ color: accentColor }}>
      {title}
    </h1>
  )

  const body = (
    <div className="flex h-full w-full flex-col">
      {heading}
      {effectiveLayout === 'STACKED' ? (
        <CanvasStackedContent elements={elements} textColor={textColor} accentColor={accentColor} fadeColor={fadeColor} />
      ) : (
        <CanvasSplitContent
          effectiveLayout={effectiveLayout}
          elements={elements}
          textColor={textColor}
          accentColor={accentColor}
          fadeColor={fadeColor}
          columnBackground={template?.background_css ?? '#ffffff'}
          imageColumnWidth={imageColumnWidth}
        />
      )}
    </div>
  )

  if (!template) return body

  return (
    <div className="h-full w-full" style={{ background: template.background_css }}>
      {body}
    </div>
  )
}

interface CanvasStackedContentProps {
  elements: SlideElement[]
  textColor?: string
  accentColor?: string
  fadeColor: string | null
}

// STACKED, canvasMode: the whole region below the heading scrolls as one
// unit if content overflows, and centers both ways when it doesn't — the
// classic flex+margin:auto trick (not justify-content/align-items: center,
// which clips overflowing content at the top in some browsers instead of
// letting it scroll into view). A lone media element renders large/centered
// instead of at its normal small capped size, since it's the whole slide.
function CanvasStackedContent({ elements, textColor, accentColor, fadeColor }: CanvasStackedContentProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const { hasOverflow, atBottom } = useScrollOverflow(scrollRef, contentRef)

  const dominantElement =
    elements.length === 1 && DOMINANT_ELEMENT_TYPES.includes(elements[0].element_type) ? elements[0] : null

  return (
    <div className="min-h-0 flex-1">
      <div ref={scrollRef} className="slide-canvas-scroll flex h-full w-full flex-col overflow-y-auto">
        {elements.length === 0 ? (
          <div ref={contentRef} className="flex h-full items-center justify-center px-6 py-6">
            <p className="text-sm text-neutral-400" style={{ color: textColor }}>
              This slide has no content yet.
            </p>
          </div>
        ) : dominantElement ? (
          <div ref={contentRef} className="flex h-full items-center justify-center px-6 py-6">
            <ElementPreview element={dominantElement} textColor={textColor} accentColor={accentColor} dominant />
          </div>
        ) : (
          <div ref={contentRef} className="m-auto w-full max-w-3xl space-y-6 px-6 py-6">
            {elements.map((element) => (
              <ElementPreview key={element.id} element={element} textColor={textColor} accentColor={accentColor} />
            ))}
          </div>
        )}
        {/* Sticky (not a sibling positioned absolutely over scrollRef) so it
            pins to scrollRef's own visible bottom edge as you scroll,
            without depending on an ancestor's height exactly matching
            scrollRef's — see ScrollHint's own comment for why that matters. */}
        <ScrollHint visible={hasOverflow && !atBottom} fadeColor={fadeColor} />
      </div>
    </div>
  )
}

interface CanvasSplitContentProps {
  effectiveLayout: 'IMAGE_LEFT' | 'IMAGE_RIGHT'
  elements: SlideElement[]
  textColor?: string
  accentColor?: string
  fadeColor: string | null
  // The slide's current background (template color, or white if none) —
  // painted behind the docked image so contain's letterboxing blends in as
  // a border instead of reading as a gap or glitch.
  columnBackground: string
  imageColumnWidth: ImageColumnWidth
}

// IMAGE_LEFT/IMAGE_RIGHT, canvasMode: a fixed-height row. The image column
// never scrolls and never crops (object-fit: contain, whole image always
// visible); the text column scrolls independently within its own region.
function CanvasSplitContent({
  effectiveLayout,
  elements,
  textColor,
  accentColor,
  fadeColor,
  columnBackground,
  imageColumnWidth,
}: CanvasSplitContentProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const { hasOverflow, atBottom } = useScrollOverflow(scrollRef, contentRef)

  const dockedElement = findDockedElement(elements)!
  const restElements = elements.filter((element) => element.id !== dockedElement.id)

  // p-6 matches the text column's own px-6 py-6 (and the heading's px-6),
  // so the image's rendered top edge lines up with the text column's first
  // line and the image never touches the canvas border on any side — the
  // column's own background (matched to the slide's background) fills the
  // padded gap too, so it reads as a border, not a seam.
  //
  // An IMAGE column hugs the image's own rendered width (w-fit) instead of
  // reserving a fixed percentage — ElementPreview sizes the img itself to
  // height:100%/width:auto, so its rendered width is purely a function of
  // the image's intrinsic aspect ratio at this column's fixed height, and
  // w-fit here just shrink-wraps that. The per-slide imageColumnWidth cap
  // (Compact/Standard/Wide — IMAGE_COLUMN_MAX_WIDTH_CLASS) bounds how far a
  // wide landscape image can push into the text column's space; once
  // clamped, fit-content's own defined behavior (min(max-content, available
  // space)) shrinks the figure to that capped width for real, which is what
  // makes the img's max-w-full (a plain CSS rule, not JS) kick in afterwards
  // and fall back to letterboxed contain sizing — see ElementPreview's IMAGE
  // coverFill branch for the other half of this. VIDEO_AUDIO keeps its own,
  // unrelated fixed 40% edge-to-edge column, unaffected by this per-slide
  // setting; this w-fit/max-w treatment is IMAGE-specific.
  const imageColumn = (
    <div
      className={`slide-canvas-image-col h-full shrink-0 p-6 ${
        dockedElement.element_type === 'IMAGE' ? `w-fit ${IMAGE_COLUMN_MAX_WIDTH_CLASS[imageColumnWidth]}` : 'w-[40%]'
      }`}
      style={{ background: columnBackground }}
    >
      <ElementPreview element={dockedElement} textColor={textColor} accentColor={accentColor} coverFill />
    </div>
  )

  const textColumn = (
    <div className="min-w-0 flex-1">
      <div ref={scrollRef} className="slide-canvas-scroll flex h-full w-full flex-col overflow-y-auto">
        {restElements.length === 0 ? (
          <p className="px-6 py-6 text-sm text-neutral-400" style={{ color: textColor }}>
            This slide has no content yet.
          </p>
        ) : (
          <div ref={contentRef} className="space-y-6 px-6 py-6">
            {restElements.map((element) => (
              <ElementPreview key={element.id} element={element} textColor={textColor} accentColor={accentColor} />
            ))}
          </div>
        )}
        <ScrollHint visible={hasOverflow && !atBottom} fadeColor={fadeColor} />
      </div>
    </div>
  )

  return (
    <div className="slide-canvas-row flex min-h-0 flex-1">
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
}
