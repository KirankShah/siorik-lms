export function formatFileSize(bytes: number): string {
  if (!bytes || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** exponent
  return `${exponent === 0 ? value : value.toFixed(1)} ${units[exponent]}`
}

export type FileKind = 'pdf' | 'word' | 'powerpoint' | 'excel' | 'archive' | 'image' | 'video' | 'audio' | 'generic'

const EXTENSION_KINDS: Record<string, FileKind> = {
  pdf: 'pdf',
  doc: 'word',
  docx: 'word',
  ppt: 'powerpoint',
  pptx: 'powerpoint',
  xls: 'excel',
  xlsx: 'excel',
  csv: 'excel',
  zip: 'archive',
  rar: 'archive',
  '7z': 'archive',
  png: 'image',
  jpg: 'image',
  jpeg: 'image',
  gif: 'image',
  webp: 'image',
  svg: 'image',
  mp4: 'video',
  mov: 'video',
  webm: 'video',
  mp3: 'audio',
  wav: 'audio',
  m4a: 'audio',
}

export function fileKindFromName(name: string): FileKind {
  const extension = name.split('.').pop()?.toLowerCase() ?? ''
  return EXTENSION_KINDS[extension] ?? 'generic'
}

// Small colored badge text — avoids pulling in an icon library just for this.
export const FILE_KIND_BADGES: Record<FileKind, { label: string; className: string }> = {
  pdf: { label: 'PDF', className: 'bg-red-100 text-red-700' },
  word: { label: 'DOC', className: 'bg-blue-100 text-blue-700' },
  powerpoint: { label: 'PPT', className: 'bg-orange-100 text-orange-700' },
  excel: { label: 'XLS', className: 'bg-emerald-100 text-emerald-700' },
  archive: { label: 'ZIP', className: 'bg-amber-100 text-amber-700' },
  image: { label: 'IMG', className: 'bg-purple-100 text-purple-700' },
  video: { label: 'VID', className: 'bg-pink-100 text-pink-700' },
  audio: { label: 'AUD', className: 'bg-indigo-100 text-indigo-700' },
  generic: { label: 'FILE', className: 'bg-slate-100 text-slate-600' },
}
