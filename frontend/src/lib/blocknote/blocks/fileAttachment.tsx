import { useRef, useState } from 'react'
import { createReactBlockSpec } from '@blocknote/react'
import type { ReactCustomBlockRenderProps } from '@blocknote/react'
import { uploadMedia } from '../../mediaApi'
import { fileKindFromName, formatFileSize, FILE_KIND_BADGES } from '../format'

const fileAttachmentConfig = {
  type: 'fileAttachment',
  propSchema: {
    url: { default: '' },
    name: { default: '' },
    size: { default: 0 },
  },
  content: 'none',
} as const

function FileAttachmentBlockRender({ block, editor }: ReactCustomBlockRenderProps<typeof fileAttachmentConfig>) {
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  async function handleUpload(files: FileList | null) {
    const file = files?.[0]
    if (!file) return
    setIsUploading(true)
    try {
      const media = await uploadMedia(file)
      editor.updateBlock(block, { props: { url: media.url, name: media.name, size: media.size } })
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  if (!block.props.url) {
    if (!editor.isEditable) return <p className="text-sm text-slate-400 italic">No file attached.</p>
    return (
      <div className="w-full rounded-lg border border-dashed border-slate-300 p-4 text-center">
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {isUploading ? 'Uploading…' : 'Attach a file'}
        </button>
        <p className="mt-1 text-xs text-slate-400">PDF, PPTX, DOCX, or any file</p>
        <input ref={fileInputRef} type="file" className="hidden" onChange={(e) => void handleUpload(e.target.files)} />
      </div>
    )
  }

  const badge = FILE_KIND_BADGES[fileKindFromName(block.props.name)]

  return (
    <div className="flex w-full max-w-md items-center gap-3 rounded-lg border border-slate-200 bg-white p-3">
      <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-md text-[10px] font-bold ${badge.className}`}>
        {badge.label}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-800">{block.props.name}</p>
        <p className="text-xs text-slate-400">{formatFileSize(block.props.size)}</p>
      </div>
      <a
        href={block.props.url}
        download={block.props.name}
        contentEditable={false}
        className="shrink-0 rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
      >
        Download
      </a>
      {editor.isEditable && (
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => editor.updateBlock(block, { props: { url: '', name: '', size: 0 } })}
          className="shrink-0 text-slate-300 hover:text-red-500"
          aria-label="Remove attachment"
        >
          ×
        </button>
      )}
    </div>
  )
}

export const fileAttachmentBlock = createReactBlockSpec(fileAttachmentConfig, { render: FileAttachmentBlockRender })
