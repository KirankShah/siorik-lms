import { useCallback, useEffect, useRef, useState } from 'react'
import '@blocknote/core/fonts/inter.css'
import { SuggestionMenuController, useCreateBlockNote } from '@blocknote/react'
import { BlockNoteView } from '@blocknote/mantine'
import '@blocknote/mantine/style.css'
import { fetchPage, savePageContent } from '../../lib/pagesApi'
import type { PageDetail } from '../../types/courses'
import { schema } from '../../lib/blocknote/schema'
import type { PageBlock } from '../../lib/blocknote/editorType'
import { getSlashMenuItems } from '../../lib/blocknote/slashMenuItems'
import { uploadFile } from '../../lib/blocknote/uploadFile'

const AUTOSAVE_DEBOUNCE_MS = 2500

type SaveState = 'idle' | 'unsaved' | 'saving' | 'saved' | 'error'

type PreviewBreakpoint = 'full' | 'desktop' | 'tablet' | 'mobile'

const PREVIEW_BREAKPOINTS: { value: PreviewBreakpoint; label: string; width: string | null }[] = [
  { value: 'full', label: 'Full width', width: null },
  { value: 'desktop', label: 'Desktop', width: '1280px' },
  { value: 'tablet', label: 'Tablet', width: '768px' },
  { value: 'mobile', label: 'Mobile', width: '390px' },
]

function toInitialContent(contentJson: unknown): PageBlock[] | undefined {
  return Array.isArray(contentJson) && contentJson.length > 0 ? (contentJson as PageBlock[]) : undefined
}

interface PageEditorProps {
  pageId: number
}

// Loads the Page by id and hands off to PageEditorSurface once it's available.
// Keyed by page.id below so switching to a different page fully remounts the
// BlockNote editor(s) — initialContent is only read once, on creation.
export function PageEditor({ pageId }: PageEditorProps) {
  const [page, setPage] = useState<PageDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    setPage(null)
    setLoadError(null)
    fetchPage(pageId)
      .then(setPage)
      .catch(() => setLoadError('Could not load this page.'))
  }, [pageId])

  if (loadError) return <p className="text-sm text-red-600">{loadError}</p>
  if (!page) return <p className="text-sm text-slate-500">Loading page…</p>

  return <PageEditorSurface key={page.id} page={page} />
}

function SaveIndicator({ state }: { state: SaveState }) {
  if (state === 'idle') return null
  const label: Record<Exclude<SaveState, 'idle'>, string> = {
    unsaved: 'Unsaved changes',
    saving: 'Saving…',
    saved: 'Saved',
    error: "Couldn't save — will retry on next edit",
  }
  const color: Record<Exclude<SaveState, 'idle'>, string> = {
    unsaved: 'text-slate-400',
    saving: 'text-slate-500',
    saved: 'text-emerald-600',
    error: 'text-red-600',
  }
  return <span className={`text-xs font-medium ${color[state]}`}>{label[state]}</span>
}

function PageEditorSurface({ page }: { page: PageDetail }) {
  const editor = useCreateBlockNote({ schema, uploadFile, initialContent: toInitialContent(page.content_json) })
  const previewEditor = useCreateBlockNote({ schema, initialContent: toInitialContent(page.content_json) })

  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [showPreview, setShowPreview] = useState(false)
  const [previewBreakpoint, setPreviewBreakpoint] = useState<PreviewBreakpoint>('full')

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latestDocumentRef = useRef<PageBlock[]>(editor.document)
  const showPreviewRef = useRef(showPreview)

  useEffect(() => {
    showPreviewRef.current = showPreview
    if (showPreview) {
      previewEditor.replaceBlocks(previewEditor.document, latestDocumentRef.current)
    }
  }, [showPreview, previewEditor])

  const save = useCallback(async () => {
    setSaveState('saving')
    try {
      await savePageContent(page.id, latestDocumentRef.current)
      setSaveState('saved')
    } catch {
      setSaveState('error')
    }
  }, [page.id])

  useEffect(() => {
    const unsubscribe = editor.onChange(() => {
      latestDocumentRef.current = editor.document
      setSaveState('unsaved')

      if (showPreviewRef.current) {
        previewEditor.replaceBlocks(previewEditor.document, editor.document)
      }

      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        void save()
      }, AUTOSAVE_DEBOUNCE_MS)
    })

    return () => {
      unsubscribe()
      // Flush a pending edit rather than dropping it when navigating away mid-debounce.
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
        void save()
      }
    }
  }, [editor, previewEditor, save])

  const activeBreakpoint = PREVIEW_BREAKPOINTS.find((bp) => bp.value === previewBreakpoint)!

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{page.title}</h2>
          <p className="text-xs text-slate-400">{page.page_type} page</p>
        </div>

        <div className="flex items-center gap-4">
          <SaveIndicator state={saveState} />

          {/*
            BlockNote already ships block-level undo/redo (ProseMirror's
            history plugin, on by default — Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z
            already work without any wiring). These buttons just surface that
            existing editor.undo()/redo() rather than reimplementing history.
          */}
          <div className="flex items-center gap-1 rounded-md border border-slate-200 p-0.5">
            <button
              type="button"
              onClick={() => editor.undo()}
              title="Undo (Ctrl+Z)"
              className="rounded px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100"
            >
              ↶ Undo
            </button>
            <button
              type="button"
              onClick={() => editor.redo()}
              title="Redo (Ctrl+Shift+Z)"
              className="rounded px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100"
            >
              ↷ Redo
            </button>
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={showPreview} onChange={(e) => setShowPreview(e.target.checked)} />
            Live preview
          </label>

          {showPreview && (
            <div className="flex items-center gap-1 rounded-md border border-slate-200 p-0.5">
              {PREVIEW_BREAKPOINTS.map((bp) => (
                <button
                  key={bp.value}
                  type="button"
                  onClick={() => setPreviewBreakpoint(bp.value)}
                  className={`rounded px-2 py-1 text-xs font-medium transition ${
                    previewBreakpoint === bp.value ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-100'
                  }`}
                >
                  {bp.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className={showPreview ? 'grid grid-cols-1 gap-4 lg:grid-cols-2' : ''}>
        <div className="rounded-xl border border-slate-200 bg-white">
          <BlockNoteView editor={editor} theme="light" slashMenu={false}>
            <SuggestionMenuController triggerCharacter="/" getItems={(query) => getSlashMenuItems(editor, query)} />
          </BlockNoteView>
        </div>

        {showPreview && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="mb-2 text-xs font-medium text-slate-400">
              Preview{activeBreakpoint.width ? ` — ${activeBreakpoint.label} (${activeBreakpoint.width})` : ''}
            </p>
            <div className="overflow-x-auto">
              <div
                className="mx-auto rounded-lg border border-slate-200 bg-white"
                style={{ width: activeBreakpoint.width ?? '100%', maxWidth: '100%' }}
              >
                <BlockNoteView editor={previewEditor} editable={false} theme="light" />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
