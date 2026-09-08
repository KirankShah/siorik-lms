import { describe, expect, it } from 'vitest'
import { extractBlankIndexes, splitBlankSegments } from './fillBlankMarkup'
import { htmlToPlainText } from './htmlEntities'

describe('htmlToPlainText', () => {
  it('leaves plain text untouched', () => {
    expect(htmlToPlainText('Money laundering has three stages: {{1}}, {{2}}, {{3}}.')).toBe(
      'Money laundering has three stages: {{1}}, {{2}}, {{3}}.',
    )
  })

  it('strips Quill tags and decodes entities, keeping the blanks', () => {
    const html =
      '<p><strong>1.&quot;The&nbsp;board&nbsp;approves&nbsp;the&nbsp;organization&#39;s&nbsp;{{1}},&nbsp;which...&quot;</strong></p>'
    expect(htmlToPlainText(html)).toBe('1."The board approves the organization\'s {{1}}, which..."')
  })

  it('turns paragraph boundaries into newlines', () => {
    expect(htmlToPlainText('<p>First {{1}}.</p><p>Second {{2}}.</p>')).toBe('First {{1}}.\nSecond {{2}}.')
  })
})

describe('splitBlankSegments', () => {
  it('splits HTML-authored question text into clean text + blank indexes', () => {
    const segments = splitBlankSegments('<p>Stages are&nbsp;{{1}} and {{2}}.</p>')
    expect(segments).toEqual(['Stages are ', 1, ' and ', 2, '.'])
  })

  it('still finds blank indexes in HTML-authored text', () => {
    expect(extractBlankIndexes('<p><strong>{{1}}</strong> then {{3}}</p>')).toEqual([1, 3])
  })
})
