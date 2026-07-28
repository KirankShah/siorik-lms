import type { BlockNoteEditor, PartialBlock } from '@blocknote/core'
import type { schema } from './schema'

export type BlockNoteEditorType = BlockNoteEditor<
  typeof schema.blockSchema,
  typeof schema.inlineContentSchema,
  typeof schema.styleSchema
>

export type PageBlock = PartialBlock<typeof schema.blockSchema, typeof schema.inlineContentSchema, typeof schema.styleSchema>
