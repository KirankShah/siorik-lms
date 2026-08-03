// FILL_BLANK question_text supports numbered placeholders like
// "Money laundering has three stages: {{1}}, {{2}}, and {{3}}." — shared by
// both fill_blank_mode variants (TEXT_INPUT renders a text box per blank,
// WORD_BANK a drop target).
const BLANK_PATTERN = /\{\{(\d+)\}\}/g

// Splits question text into an alternating array of plain-text strings and
// blank-index numbers, so player components can map it directly to React
// elements (text segments as text, numbers as an inline input/drop target) —
// no HTML injection, DOM querying, or portals involved.
export function splitBlankSegments(text: string): (string | number)[] {
  return text.split(BLANK_PATTERN).map((part, i) => (i % 2 === 1 ? Number(part) : part)).filter((part) => part !== '')
}

export function extractBlankIndexes(text: string): number[] {
  const indexes: number[] = []
  const pattern = new RegExp(BLANK_PATTERN)
  let match: RegExpExecArray | null
  while ((match = pattern.exec(text)) !== null) {
    indexes.push(Number(match[1]))
  }
  return indexes
}
