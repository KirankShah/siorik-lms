import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('resource viewer hosting configuration', () => {
  it('serves the PDF.js module worker with a JavaScript MIME type', () => {
    const rewriteRules = readFileSync(resolve(process.cwd(), 'public', '.htaccess'), 'utf8')

    expect(rewriteRules).toContain('AddType application/javascript .mjs')
  })
})
