import { uploadMedia } from '../mediaApi'

// Wired into useCreateBlockNote({ uploadFile }) — used by the default image
// and audio blocks' built-in "add file" UI. All custom media blocks
// (imageGallery, video, fileAttachment) call uploadMedia() directly instead,
// since they need more than just the URL back (size, multi-file, etc.), but
// everything routes through the same backend endpoint either way.
export async function uploadFile(file: File): Promise<string> {
  const media = await uploadMedia(file)
  return media.url
}
