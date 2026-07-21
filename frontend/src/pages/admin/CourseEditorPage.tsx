import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AccessGrantsPanel } from '../../components/admin/AccessGrantsPanel'
import { ModuleEditor } from '../../components/admin/ModuleEditor'
import { QuizList } from '../../components/admin/QuizList'
import { useAuth } from '../../context/AuthContext'
import { fetchOrganizations } from '../../lib/accountsApi'
import { createCourse, createModule, fetchCourseDetail, updateCourse } from '../../lib/coursesApi'
import { slugify } from '../../lib/slugify'
import type { Organization } from '../../types/auth'
import type { CourseDetail } from '../../types/courses'

export function CourseEditorPage() {
  const { slug: slugParam } = useParams<{ slug: string }>()
  const isCreateMode = !slugParam
  const navigate = useNavigate()
  const { user } = useAuth()
  const isPlatformAdmin = user?.role === 'PLATFORM_ADMIN'

  const [course, setCourse] = useState<CourseDetail | null>(null)
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  const [title, setTitle] = useState('')
  const [slug, setSlug] = useState('')
  const [slugTouched, setSlugTouched] = useState(false)
  const [description, setDescription] = useState('')
  const [organizationId, setOrganizationId] = useState<number | ''>('')
  const [isPublished, setIsPublished] = useState(false)
  const [coverImage, setCoverImage] = useState<File | null>(null)

  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const [isAddingModule, setIsAddingModule] = useState(false)
  const [newModuleTitle, setNewModuleTitle] = useState('')

  useEffect(() => {
    if (isPlatformAdmin) {
      fetchOrganizations().then(setOrganizations).catch(() => {})
    }
  }, [isPlatformAdmin])

  function loadCourse(slugToLoad: string) {
    fetchCourseDetail(slugToLoad)
      .then((detail) => {
        setCourse(detail)
        setTitle(detail.title)
        setSlug(detail.slug)
        setDescription(detail.description)
        setOrganizationId(detail.organization ?? '')
        setIsPublished(detail.is_published)
      })
      .catch(() => setLoadError('Could not load this course.'))
  }

  useEffect(() => {
    if (slugParam) loadCourse(slugParam)
  }, [slugParam])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setIsSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    try {
      const payload = {
        title,
        slug,
        description,
        organization: isPlatformAdmin ? (organizationId === '' ? null : Number(organizationId)) : null,
        is_published: isPublished,
        cover_image: coverImage,
      }
      if (isCreateMode) {
        const created = await createCourse(payload)
        navigate(`/admin/courses/${created.slug}/edit`, { replace: true })
      } else {
        const updated = await updateCourse(slugParam!, payload)
        setCourse(updated)
        setSaveSuccess(true)
      }
    } catch {
      setSaveError('Could not save the course. Check the slug is unique and try again.')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleAddModule() {
    if (!course || !newModuleTitle.trim()) return
    try {
      await createModule({ course: course.id, title: newModuleTitle, order: course.modules.length + 1 })
      setNewModuleTitle('')
      setIsAddingModule(false)
      loadCourse(course.slug)
    } catch {
      setLoadError('Could not create module.')
    }
  }

  if (loadError) return <p className="text-sm text-red-600">{loadError}</p>
  if (!isCreateMode && !course) return <p className="text-sm text-slate-500">Loading course…</p>

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-lg font-semibold text-slate-900">{isCreateMode ? 'New Course' : 'Course Details'}</h1>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">Title</label>
            <input
              required
              value={title}
              onChange={(e) => {
                setTitle(e.target.value)
                if (!slugTouched) setSlug(slugify(e.target.value))
              }}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">Slug</label>
            <input
              required
              value={slug}
              onChange={(e) => {
                setSlug(e.target.value)
                setSlugTouched(true)
              }}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>

          <div>
            <p className="text-sm font-medium text-slate-700">Content owner</p>
            <p className="mt-1 text-sm text-slate-500">
              {isPlatformAdmin
                ? 'Platform — courses you create are platform-managed. Organizations only see it once granted access below.'
                : "Organization — this course belongs to your organization's own self-serve content and is scoped to your org automatically."}
            </p>
          </div>

          {isPlatformAdmin && (
            <div>
              <label className="block text-sm font-medium text-slate-700">Organization (metadata only)</label>
              <select
                value={organizationId}
                onChange={(e) => setOrganizationId(e.target.value === '' ? '' : Number(e.target.value))}
                className="mt-1 w-full max-w-xs rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">None</option>
                {organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-slate-400">
                Doesn't control visibility for platform courses — use the access grants below for that.
              </p>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-slate-700">Cover image</label>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setCoverImage(e.target.files?.[0] ?? null)}
              className="mt-1 text-sm"
            />
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={isPublished} onChange={(e) => setIsPublished(e.target.checked)} />
            Published
          </label>

          {saveError && <p className="text-sm text-red-600">{saveError}</p>}
          {saveSuccess && <p className="text-sm text-emerald-600">Saved.</p>}

          <button
            type="submit"
            disabled={isSaving}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:opacity-60"
          >
            {isSaving ? 'Saving…' : isCreateMode ? 'Create Course' : 'Save Changes'}
          </button>
        </form>
      </div>

      {course && (
        <>
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">Curriculum</h2>
            <div className="mt-4 space-y-4">
              {course.modules.map((module) => (
                <ModuleEditor key={module.id} module={module} onChanged={() => loadCourse(course.slug)} />
              ))}
            </div>

            {isAddingModule ? (
              <div className="mt-4 flex items-center gap-2">
                <input
                  value={newModuleTitle}
                  onChange={(e) => setNewModuleTitle(e.target.value)}
                  placeholder="Module title"
                  className="rounded border border-slate-300 px-2 py-1 text-sm"
                />
                <button type="button" onClick={handleAddModule} className="text-sm font-medium text-emerald-700">
                  Add
                </button>
                <button type="button" onClick={() => setIsAddingModule(false)} className="text-sm text-slate-500">
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setIsAddingModule(true)}
                className="mt-4 text-sm font-medium text-slate-900 hover:underline"
              >
                + Add module
              </button>
            )}
          </div>

          <QuizList
            courseId={course.id}
            courseSlug={course.slug}
            quizzes={course.quizzes}
            onChanged={() => loadCourse(course.slug)}
          />

          {isPlatformAdmin && course.content_owner === 'PLATFORM' && (
            <AccessGrantsPanel
              courseSlug={course.slug}
              grants={course.access_grants}
              organizations={organizations}
              onChanged={() => loadCourse(course.slug)}
            />
          )}
        </>
      )}
    </div>
  )
}
