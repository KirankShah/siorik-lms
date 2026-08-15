import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import '@testing-library/jest-dom/vitest'

// RTL's automatic afterEach-cleanup only self-registers when it detects a
// global `afterEach` (i.e. vitest's `globals: true`) — since this project
// deliberately imports test globals explicitly instead, register it here.
afterEach(() => {
  cleanup()
})

// jsdom has no ResizeObserver implementation at all — any test that renders
// a canvasMode slide (ScrollHint, used by SlideElementsView's
// CanvasStackedContent/CanvasSplitContent) throws ReferenceError without
// this. A no-op stub is enough: these tests only assert on gating/content,
// never on scroll-overflow behavior.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// Cast (not @ts-expect-error) since whether this errors depends on which
// tsconfig project picks up this file — an unmet @ts-expect-error is itself
// a type error under tsc -b's project-build step.
;(globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }).ResizeObserver = ResizeObserverStub
