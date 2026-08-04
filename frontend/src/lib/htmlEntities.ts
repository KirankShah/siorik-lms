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
