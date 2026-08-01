import type { ElementType, Layout, SlideElement } from '../types/slides'

const DOCKABLE_ELEMENT_TYPES: ElementType[] = ['IMAGE', 'VIDEO_AUDIO']

// IMAGE_LEFT/IMAGE_RIGHT dock the slide's first Image or Video element into a
// column of their own. If a slide has neither, that column would render
// empty, so both the authoring preview and the student view fall back to
// STACKED automatically rather than showing a broken split.
export function resolveEffectiveLayout(layout: Layout, elements: SlideElement[]): Layout {
  if (layout === 'STACKED') return 'STACKED'
  const hasDockableElement = elements.some((element) => DOCKABLE_ELEMENT_TYPES.includes(element.element_type))
  return hasDockableElement ? layout : 'STACKED'
}

export function findDockedElement(elements: SlideElement[]): SlideElement | undefined {
  return elements.find((element) => DOCKABLE_ELEMENT_TYPES.includes(element.element_type))
}
