import { useEffect } from 'react'
import type { ClipboardEvent, MouseEvent, ReactNode } from 'react'

// NOTE ON SCOPE: none of this is a real security boundary. There is no
// browser API that detects or blocks OS-level screen capture, and anyone
// with devtools already open (or who just disables JavaScript) bypasses
// every check below trivially. This only raises the bar against casual
// right-click "Save As"/copy-paste and an opportunistic "view source" —
// it deters, it does not prevent. Pair with WatermarkOverlay for actual
// traceability if content leaks anyway.

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable
}

function isDevToolsShortcut(e: KeyboardEvent): boolean {
  if (e.key === 'F12') return true
  const mod = e.ctrlKey || e.metaKey
  if (!mod) return false
  const key = e.key.toLowerCase()
  if (e.shiftKey && (key === 'i' || key === 'j' || key === 'c')) return true // devtools / console / inspect-element
  if (!e.shiftKey && key === 'u') return true // view-source
  return false
}

interface ContentProtectionBoundaryProps {
  children: ReactNode
}

// Wraps a slide's rendered content (any slide type) to deter casual
// copying — scoped to exactly this subtree, never the sidebar/nav/footer
// around it, which stay normally usable. Editable form fields (short-
// answer/essay/fill-blank inputs a learner types their own answer into)
// are deliberately exempted from the copy/cut/paste/context-menu block, so
// answering a question is unaffected — only the surrounding read-only
// content is protected.
export function ContentProtectionBoundary({ children }: ContentProtectionBoundaryProps) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (isDevToolsShortcut(e)) e.preventDefault()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  function block(e: MouseEvent | ClipboardEvent) {
    if (isEditableTarget(e.target)) return
    e.preventDefault()
  }

  return (
    // h-full: transparent to the fullscreen CONTENT layout, which needs an
    // unbroken chain of definite heights from FullscreenSlideOverlay's
    // flex-1 well down to SlideCanvas's own h-full flex-col — this wrapper
    // sits in the middle of that chain and must not collapse it. Harmless
    // for every other slide type/layout, which are width- not height-driven.
    <div
      className="h-full"
      onContextMenu={block}
      onCopy={block}
      onCut={block}
      onPaste={block}
      style={{ userSelect: 'none', WebkitUserSelect: 'none' }}
    >
      {children}
    </div>
  )
}
