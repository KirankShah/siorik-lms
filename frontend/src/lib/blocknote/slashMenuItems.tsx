import { filterSuggestionItems, insertOrUpdateBlockForSlashMenu } from '@blocknote/core/extensions'
import { getDefaultReactSlashMenuItems } from '@blocknote/react'
import type { DefaultReactSuggestionItem } from '@blocknote/react'
import type { BlockNoteEditorType } from './editorType'

function emojiIcon(emoji: string) {
  return <span className="text-base leading-none">{emoji}</span>
}

function customSlashMenuItems(editor: BlockNoteEditorType): DefaultReactSuggestionItem[] {
  return [
    {
      title: 'Image Gallery',
      subtext: 'Multiple images in a grid or carousel',
      aliases: ['gallery', 'images', 'carousel'],
      group: 'Media',
      icon: emojiIcon('🖼️'),
      onItemClick: () => insertOrUpdateBlockForSlashMenu(editor, { type: 'imageGallery' }),
    },
    {
      title: 'Callout',
      subtext: 'Note, tip, warning, or info box',
      aliases: ['note', 'tip', 'warning', 'info', 'alert'],
      group: 'Basic blocks',
      icon: emojiIcon('💬'),
      onItemClick: () => insertOrUpdateBlockForSlashMenu(editor, { type: 'callout' }),
    },
    {
      title: 'Accordion',
      subtext: 'Expandable section',
      aliases: ['collapse', 'expand', 'toggle'],
      group: 'Basic blocks',
      icon: emojiIcon('📂'),
      onItemClick: () =>
        insertOrUpdateBlockForSlashMenu(editor, {
          type: 'accordionItem',
          content: 'Section title',
        }),
    },
    {
      title: 'FAQ Item',
      subtext: 'Question and answer pair',
      aliases: ['faq', 'question'],
      group: 'Basic blocks',
      icon: emojiIcon('❓'),
      onItemClick: () =>
        insertOrUpdateBlockForSlashMenu(editor, {
          type: 'faqItem',
          content: 'Question?',
        }),
    },
    {
      title: 'Tabs',
      subtext: 'Switchable sections',
      aliases: ['tab', 'tabbed'],
      group: 'Basic blocks',
      icon: emojiIcon('🗂️'),
      onItemClick: () =>
        insertOrUpdateBlockForSlashMenu(editor, {
          type: 'tabs',
          children: [
            { type: 'tabPanel', props: { label: 'Tab 1', isActive: true }, children: [{ type: 'paragraph' }] },
            { type: 'tabPanel', props: { label: 'Tab 2', isActive: false }, children: [{ type: 'paragraph' }] },
          ],
        }),
    },
    {
      title: 'Button',
      subtext: 'Link styled as a button',
      aliases: ['link', 'cta'],
      group: 'Basic blocks',
      icon: emojiIcon('🔘'),
      onItemClick: () => insertOrUpdateBlockForSlashMenu(editor, { type: 'button' }),
    },
  ]
}

export async function getSlashMenuItems(editor: BlockNoteEditorType, query: string): Promise<DefaultReactSuggestionItem[]> {
  const items = [...getDefaultReactSlashMenuItems(editor), ...customSlashMenuItems(editor)]
  return filterSuggestionItems(items, query)
}
