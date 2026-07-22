import { useState } from 'react'
import { Link } from 'react-router-dom'
import { createPage, deletePage } from '../../lib/pagesApi'
import type { PageSummary, PageType } from '../../types/courses'

interface PageListProps {
  lessonId: number
  pages: PageSummary[]
  onChanged: () => void
}

const PAGE_TYPES: PageType[] = ['CONTENT', 'QUIZ', 'ASSIGNMENT']

export function PageList({ lessonId, pages, onChanged }: PageListProps) {
  const [isAdding, setIsAdding] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newType, setNewType] = useState<PageType>('CONTENT')
  const [error, setError] = useState<string | null>(null)

  async function handleAddPage() {
    if (!newTitle.trim()) return
    try {
      await createPage({
        lesson: lessonId,
        title: newTitle,
        page_type: newType,
        order: pages.length + 1,
      })
      setNewTitle('')
      setIsAdding(false)
      onChanged()
    } catch {
      setError('Could not create page.')
    }
  }

  async function handleDeletePage(page: PageSummary) {
    if (!window.confirm(`Delete page "${page.title}"?`)) return
    try {
      await deletePage(page.id)
      onChanged()
    } catch {
      setError('Could not delete page.')
    }
  }

  return (
    <div className="mt-2 ml-4 space-y-1 border-l border-slate-100 pl-3">
      {pages.map((page) => (
        <div key={page.id} className="flex items-center justify-between text-xs text-slate-500">
          <Link to={`/admin/pages/${page.id}`} className="hover:underline">
            {page.order}. {page.title} <span className="text-slate-400">({page.page_type})</span>
          </Link>
          <button type="button" onClick={() => handleDeletePage(page)} className="text-red-500 hover:underline">
            Delete
          </button>
        </div>
      ))}

      {error && <p className="text-xs text-red-600">{error}</p>}

      {isAdding ? (
        <div className="flex items-center gap-2 pt-1">
          <input
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="Page title"
            className="rounded border border-slate-300 px-2 py-1 text-xs"
          />
          <select
            value={newType}
            onChange={(e) => setNewType(e.target.value as PageType)}
            className="rounded border border-slate-300 px-2 py-1 text-xs"
          >
            {PAGE_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <button type="button" onClick={handleAddPage} className="text-xs font-medium text-emerald-700">
            Add
          </button>
          <button type="button" onClick={() => setIsAdding(false)} className="text-xs text-slate-500">
            Cancel
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => setIsAdding(true)} className="pt-1 text-xs font-medium text-slate-600 hover:underline">
          + Add page
        </button>
      )}
    </div>
  )
}
