// Plain-text quiz fields (choice/match text, word bank tokens, category
// labels, etc.) are edited with ordinary <input> elements, not RichTextField.
// If HTML-entity-encoded content ends up in one anyway — e.g. pasted from a
// source that already ran it through an HTML encoder, or copied out of a
// rich-text field — decode it once here so it doesn't render as literal
// "&nbsp;"/"&quot;" text, and so a second decode pass later can't compound it.
const ENTITY_PATTERN = /&(?:[a-zA-Z][a-zA-Z0-9]*|#\d+|#x[0-9a-fA-F]+);/

export function decodeHtmlEntitiesIfPresent(text: string): string {
  if (!ENTITY_PATTERN.test(text)) return text
  const el = document.createElement('textarea')
  el.innerHTML = text
  return el.value
}

// A rich-text (Quill) value that has leaked into a field meant to hold plain
// text — most visibly FILL_BLANK question_text, which is split on {{N}} and
// rendered as React text nodes, so any tags/entities would show up literally
// ("<p>", "&nbsp;", "&quot;"). Collapses block boundaries to newlines, strips
// tags, decodes entities once. A string with no "<" or "&" is returned as-is.
export function htmlToPlainText(value: string): string {
  if (!/[<&]/.test(value)) return value
  const withBreaks = value
    .replace(/<\s*br\s*\/?\s*>/gi, '\n')
    .replace(/<\/\s*(?:p|div|li|h[1-6]|tr)\s*>/gi, '\n')
  const el = document.createElement('div')
  el.innerHTML = withBreaks
  // `\S` in a JS regex excludes U+00A0, so `[^\S\n]` is "any whitespace except
  // a newline" — collapses runs of spaces / tabs / decoded &nbsp; to one space
  // while keeping the paragraph breaks introduced above.
  return (el.textContent ?? '')
    .replace(/[^\S\n]+/g, ' ')
    .replace(/ *\n */g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}
