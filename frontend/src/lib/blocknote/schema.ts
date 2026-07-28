import { BlockNoteSchema, defaultBlockSpecs } from '@blocknote/core'
import { accordionItemBlock } from './blocks/accordionItem'
import { buttonBlock } from './blocks/button'
import { calloutBlock } from './blocks/callout'
import { faqItemBlock } from './blocks/faqItem'
import { fileAttachmentBlock } from './blocks/fileAttachment'
import { imageGalleryBlock } from './blocks/imageGallery'
import { tabPanelBlock, tabsBlock } from './blocks/tabs'
import { videoBlock } from './blocks/video'

// Extends BlockNote's default schema with the LMS's custom block types.
//
// Kept as-is from the defaults (already cover the brief without changes):
//  - image: already supports captions
//  - audio: already supports upload + playback
//  - divider, table, headings 1-6, lists, checklist, quote, code block: all defaults
//
// Overridden:
//  - video: replaced to auto-detect YouTube/Vimeo/Wistia/Loom and embed them,
//    falling back to a plain <video> for self-hosted uploads
//  - file: replaced with a download-card rendering (icon + size), matching
//    the "File Attachment" block in the brief
//
// New:
//  - imageGallery, callout, accordionItem, faqItem, tabs/tabPanel, button
export const schema = BlockNoteSchema.create({
  blockSpecs: {
    ...defaultBlockSpecs,
    video: videoBlock(),
    file: fileAttachmentBlock(),
    imageGallery: imageGalleryBlock(),
    callout: calloutBlock(),
    accordionItem: accordionItemBlock(),
    faqItem: faqItemBlock(),
    tabs: tabsBlock(),
    tabPanel: tabPanelBlock(),
    button: buttonBlock(),
  },
})
