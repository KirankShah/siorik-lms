import { useRef, useState } from 'react'
import { createReactBlockSpec } from '@blocknote/react'
import type { ReactCustomBlockRenderProps } from '@blocknote/react'
import { uploadMedia } from '../../mediaApi'

interface GalleryImage {
  url: string
  caption: string
}

function parseImages(json: string): GalleryImage[] {
  try {
    const parsed: unknown = JSON.parse(json)
    return Array.isArray(parsed) ? (parsed as GalleryImage[]) : []
  } catch {
    return []
  }
}

const imageGalleryConfig = {
  type: 'imageGallery',
  propSchema: {
    imagesJson: { default: '[]' },
    layout: { default: 'grid', values: ['grid', 'carousel'] as const },
  },
  content: 'none',
} as const

function ImageGalleryBlockRender({ block, editor }: ReactCustomBlockRenderProps<typeof imageGalleryConfig>) {
  const images = parseImages(block.props.imagesJson)
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function persist(next: GalleryImage[]) {
    editor.updateBlock(block, { props: { imagesJson: JSON.stringify(next) } })
  }

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    setIsUploading(true)
    try {
      const uploaded = await Promise.all(
        Array.from(files).map(async (file) => {
          const media = await uploadMedia(file)
          return { url: media.url, caption: '' }
        }),
      )
      persist([...images, ...uploaded])
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  function updateCaption(index: number, caption: string) {
    persist(images.map((img, i) => (i === index ? { ...img, caption } : img)))
  }

  function removeImage(index: number) {
    persist(images.filter((_, i) => i !== index))
  }

  return (
    <div className="w-full rounded-lg border border-slate-200 p-3">
      {editor.isEditable && (
        <div className="mb-3 flex items-center justify-between" contentEditable={false}>
          <div className="flex gap-1 rounded-md border border-slate-200 p-0.5">
            {(['grid', 'carousel'] as const).map((layout) => (
              <button
                key={layout}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => editor.updateBlock(block, { props: { layout } })}
                className={`rounded px-2 py-0.5 text-xs font-medium capitalize ${
                  block.props.layout === layout ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-100'
                }`}
              >
                {layout}
              </button>
            ))}
          </div>
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="rounded-md bg-slate-900 px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50"
          >
            {isUploading ? 'Uploading…' : '+ Add images'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(e) => void handleFiles(e.target.files)}
          />
        </div>
      )}

      {images.length === 0 ? (
        <p className="text-sm text-slate-400 italic">No images yet.</p>
      ) : block.props.layout === 'grid' ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {images.map((img, index) => (
            <GalleryTile
              key={img.url + index}
              image={img}
              editable={editor.isEditable}
              onCaptionChange={(c) => updateCaption(index, c)}
              onRemove={() => removeImage(index)}
            />
          ))}
        </div>
      ) : (
        <div className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-2">
          {images.map((img, index) => (
            <div key={img.url + index} className="w-56 shrink-0 snap-start">
              <GalleryTile
                image={img}
                editable={editor.isEditable}
                onCaptionChange={(c) => updateCaption(index, c)}
                onRemove={() => removeImage(index)}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function GalleryTile({
  image,
  editable,
  onCaptionChange,
  onRemove,
}: {
  image: GalleryImage
  editable: boolean
  onCaptionChange: (caption: string) => void
  onRemove: () => void
}) {
  return (
    <div className="group relative overflow-hidden rounded-md border border-slate-200 bg-slate-50">
      <img src={image.url} alt={image.caption} className="aspect-video w-full object-cover" />
      {editable && (
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={onRemove}
          className="absolute top-1 right-1 rounded-full bg-black/60 px-1.5 py-0.5 text-xs text-white opacity-0 transition group-hover:opacity-100"
          aria-label="Remove image"
        >
          ×
        </button>
      )}
      {editable ? (
        <input
          value={image.caption}
          onChange={(e) => onCaptionChange(e.target.value)}
          placeholder="Caption…"
          className="w-full border-t border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 focus:outline-none"
        />
      ) : (
        image.caption && <p className="border-t border-slate-200 bg-white px-2 py-1 text-xs text-slate-600">{image.caption}</p>
      )}
    </div>
  )
}

export const imageGalleryBlock = createReactBlockSpec(imageGalleryConfig, { render: ImageGalleryBlockRender })
