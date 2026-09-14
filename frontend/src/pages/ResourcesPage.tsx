import { useEffect, useRef, useState } from 'react'
import { FileText, Upload } from 'lucide-react'
import { Banner } from '../components/ui/Banner'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { useAuth } from '../context/AuthContext'
import { ApiError } from '../lib/apiClient'
import { deleteResource, fetchResources, uploadResource } from '../lib/resourcesApi'
import type { Resource } from '../types/resources'

function extractErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.body && typeof err.body === 'object') {
    const value = Object.values(err.body as Record<string, unknown>)[0]
    if (typeof value === 'string') return value
    if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
  }
  return fallback
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function ResourcesPage() {
  const { user } = useAuth()
  // Upload is deliberately ORG_ADMIN only — not INSTRUCTOR, not even
  // PLATFORM_ADMIN — matching the product spec exactly (a platform admin has
  // no organization to upload into anyway; see
  // resources.views.ResourceViewSet.perform_create). The server enforces
  // this independently (core.permissions.IsOrgAdminRole + the organization
  // check in perform_create) — this is UI convenience only.
  const canUpload = user?.role === 'ORG_ADMIN'

  const [resources, setResources] = useState<Resource[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function load() {
    fetchResources()
      .then(setResources)
      .catch(() => setError('Could not load resources.'))
  }

  useEffect(load, [])

  async function handleUpload() {
    if (!file) return
    setIsUploading(true)
    setUploadError(null)
    try {
      const created = await uploadResource({ title: title.trim(), description: description.trim(), file })
      setResources((prev) => [created, ...(prev ?? [])])
      setTitle('')
      setDescription('')
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (err) {
      setUploadError(extractErrorMessage(err, 'Could not upload this resource. Please try again.'))
    } finally {
      setIsUploading(false)
    }
  }

  async function handleDelete(resource: Resource) {
    if (!window.confirm(`Delete "${resource.title}"? This cannot be undone.`)) return
    setDeletingId(resource.id)
    setError(null)
    try {
      await deleteResource(resource.id)
      setResources((prev) => prev?.filter((r) => r.id !== resource.id) ?? null)
    } catch {
      setError('Could not delete this resource.')
    } finally {
      setDeletingId(null)
    }
  }

  function handleView(resource: Resource) {
    window.open(`/resources/${resource.id}/view`, '_blank', 'noopener,noreferrer')
  }

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Resources</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Documents shared by your organization, viewable in a protected reader — not downloadable through this page.
      </p>

      {error && (
        <Banner variant="warning" className="mt-4">
          {error}
        </Banner>
      )}

      {canUpload && (
        <Card className="mt-6 max-w-xl p-4">
          <h2 className="text-sm font-semibold text-neutral-900">Upload Resource</h2>
          {uploadError && <p className="mt-2 text-sm text-red-600">{uploadError}</p>}
          <div className="mt-3 space-y-3">
            <Input
              id="resource-title"
              label="Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Q3 Compliance Bulletin"
            />
            <div>
              <label htmlFor="resource-description" className="block text-sm font-medium text-neutral-700">
                Description
              </label>
              <textarea
                id="resource-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-brand-navy focus:ring-1 focus:ring-brand-navy focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700">PDF file (max 20MB)</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="mt-1 text-sm"
              />
            </div>
            <Button onClick={() => void handleUpload()} disabled={!title.trim() || !file || isUploading}>
              <Upload className="h-4 w-4" />
              {isUploading ? 'Uploading…' : 'Upload Resource'}
            </Button>
          </div>
        </Card>
      )}

      {!resources && !error && <p className="mt-6 text-sm text-neutral-400">Loading…</p>}

      {resources && resources.length === 0 && (
        <Card className="mt-6 flex flex-col items-center gap-3 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-navy/10 text-brand-navy">
            <FileText className="h-6 w-6" />
          </div>
          <p className="text-sm font-medium text-neutral-900">No resources yet</p>
          <p className="max-w-sm text-sm text-neutral-500">
            {canUpload
              ? 'Upload a PDF above to share it with every learner in your organization.'
              : "Your organization hasn't shared any documents here yet."}
          </p>
        </Card>
      )}

      {resources && resources.length > 0 && (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {resources.map((resource) => (
            <Card key={resource.id} className="flex flex-col gap-3 p-4">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-navy/10 text-brand-navy">
                  <FileText className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-neutral-900">{resource.title}</p>
                  <p className="text-xs text-neutral-400">Uploaded {formatDate(resource.uploaded_at)}</p>
                </div>
              </div>
              {resource.description && <p className="line-clamp-3 text-sm text-neutral-600">{resource.description}</p>}
              <div className="mt-auto flex items-center justify-between gap-2 pt-2">
                <Button size="sm" onClick={() => handleView(resource)}>
                  View
                </Button>
                {resource.can_delete && (
                  <button
                    type="button"
                    disabled={deletingId === resource.id}
                    onClick={() => void handleDelete(resource)}
                    className="text-xs text-red-600 underline disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {deletingId === resource.id ? 'Deleting…' : 'Delete'}
                  </button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
