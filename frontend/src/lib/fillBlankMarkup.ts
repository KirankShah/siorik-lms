// FILL_BLANK question_text supports numbered placeholders like
// "Money laundering has three stages: {{1}}, {{2}}, and {{3}}." — shared by
// both fill_blank_mode variants (TEXT_INPUT renders a text box per blank,
// WORD_BANK a drop target). This turns each {{N}} into an inline <span>
// marker that the player components portal an interactive widget into,
// preserving whatever surrounding HTML (paragraphs, formatting) RichTextField
// produced around it.
const BLANK_PATTERN = /\{\{(\d+)\}\}/g

export function injectBlankMarkup(html: string): string {
  return html.replace(BLANK_PATTERN, (_match, index: string) => `<span class="fill-blank-slot" data-blank-index="${index}"></span>`)
}

export function extractBlankIndexes(html: string): number[] {
  const indexes: number[] = []
  const pattern = new RegExp(BLANK_PATTERN)
  let match: RegExpExecArray | null
  while ((match = pattern.exec(html)) !== null) {
    indexes.push(Number(match[1]))
  }
  return indexes
}
