import { useRef, useState } from 'react'
import { createReactBlockSpec } from '@blocknote/react'
import type { ReactCustomBlockRenderProps } from '@blocknote/react'
import { uploadMedia } from '../../mediaApi'
import { resolveVideoEmbed } from '../videoProviders'

const videoConfig = {
  type: 'video',
  propSchema: {
    url: { default: '' },
    caption: { default: '' },
  },
  content: 'none',
} as const

function VideoBlockRender({ block, editor }: ReactCustomBlockRenderProps<typeof videoConfig>) {
  const [urlDraft, setUrlDraft] = useState(block.props.url)
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function setUrl(url: string) {
    editor.updateBlock(block, { props: { url } })
  }

  async function handleUpload(files: FileList | null) {
    const file = files?.[0]
    if (!file) return
    setIsUploading(true)
    try {
      const media = await uploadMedia(file)
      setUrlDraft(media.url)
      setUrl(media.url)
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  if (!block.props.url) {
    if (!editor.isEditable) return <p className="text-sm text-slate-400 italic">No video set.</p>
    return (
      <div className="w-full rounded-lg border border-dashed border-slate-300 p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (urlDraft.trim()) setUrl(urlDraft.trim())
          }}
          className="flex gap-2"
        >
          <input
            value={urlDraft}
            onChange={(e) => setUrlDraft(e.target.value)}
            placeholder="Paste a YouTube, Vimeo, Wistia, or Loom link…"
            className="flex-1 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
          <button type="submit" className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white">
            Embed
          </button>
        </form>
        <div className="mt-2 flex items-center gap-2 text-xs text-slate-400">
          <span className="h-px flex-1 bg-slate-200" />
          or
          <span className="h-px flex-1 bg-slate-200" />
        </div>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="mt-2 w-full rounded-md border border-slate-300 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          {isUploading ? 'Uploading…' : 'Upload a video file'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={(e) => void handleUpload(e.target.files)}
        />
      </div>
    )
  }

  const embed = resolveVideoEmbed(block.props.url)

  return (
    <div className="w-full">
      <div className="relative aspect-video w-full overflow-hidden rounded-lg bg-black">
        {embed?.kind === 'embed' ? (
          <iframe
            src={embed.src}
            className="absolute inset-0 h-full w-full"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            title={block.props.caption || 'Embedded video'}
          />
        ) : (
          // Self-hosted playback. No transcoding pipeline exists yet, so this
          // is a plain progressive <video> tag rather than an adaptive-bitrate
          // player. If/when the backend starts transcoding uploads to HLS,
          // swap this for hls.js (Hls.loadSource + Hls.attachMedia) with this
          // same <video> element as the target — browsers with native HLS
          // support (Safari) can keep using `src` directly.
          <video controls src={embed?.src} className="absolute inset-0 h-full w-full" />
        )}
      </div>
      {editor.isEditable && (
        <div className="mt-1 flex items-center gap-2" contentEditable={false}>
          <input
            value={block.props.caption}
            onChange={(e) => editor.updateBlock(block, { props: { caption: e.target.value } })}
            placeholder="Caption…"
            className="flex-1 rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600"
          />
          <button type="button" onClick={() => setUrl('')} className="text-xs text-slate-400 hover:text-red-500">
            Replace
          </button>
        </div>
      )}
    </div>
  )
}

export const videoBlock = createReactBlockSpec(videoConfig, { render: VideoBlockRender })
