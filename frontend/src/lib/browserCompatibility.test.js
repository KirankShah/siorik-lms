import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'
import { describe, it } from 'vitest'

const source = fs.readFileSync(
  path.resolve(process.cwd(), 'public/browser-compatibility.js'),
  'utf8',
)

function runCompatibilityCheck(userAgent) {
  const nodes = {
    'browser-compatibility-warning': {
      shown: false,
      removeAttribute(name) {
        if (name === 'hidden') this.shown = true
      },
    },
    root: {
      hidden: false,
      setAttribute(name) {
        if (name === 'hidden') this.hidden = true
      },
    },
    'browser-compatibility-url': {
      value: '',
      select() {},
    },
  }
  const window = {
    navigator: { userAgent },
    location: { href: 'https://enterprise.learnwithsiorik.com/reset-password/uid/token/' },
    document: { getElementById: (id) => nodes[id] || null },
    Promise,
    fetch() {},
    URL,
    Map,
    Set,
  }
  vm.runInNewContext(source, { window })
  return { api: window.SiorikBrowserCompatibility, nodes }
}

describe('static browser compatibility check', () => {
  it('shows the fallback with a copyable URL in Edge 108', () => {
    const { api, nodes } = runCompatibilityCheck(
      'Mozilla/5.0 Chrome/108.0.0.0 Safari/537.36 Edg/108.0.0.0',
    )

    assert.equal(api.browserSupport('Edg/108.0').supported, false)
    assert.equal(nodes['browser-compatibility-warning'].shown, true)
    assert.equal(nodes.root.hidden, true)
    assert.match(nodes['browser-compatibility-url'].value, /reset-password/)
  })

  it('allows Edge and Chrome 109 while rejecting their prior versions', () => {
    const edge = runCompatibilityCheck(
      'Mozilla/5.0 Chrome/109.0.0.0 Safari/537.36 Edg/109.0.0.0',
    )
    const chrome = runCompatibilityCheck(
      'Mozilla/5.0 Chrome/109.0.0.0 Safari/537.36',
    )

    assert.equal(edge.api.browserSupport('Edg/109.0').supported, true)
    assert.equal(edge.nodes['browser-compatibility-warning'].shown, false)
    assert.equal(chrome.api.browserSupport('Chrome/109.0').supported, true)
    assert.equal(chrome.api.browserSupport('Chrome/108.0').supported, false)
  })

  it('rejects Edge Legacy and Internet Explorer', () => {
    const { api } = runCompatibilityCheck('Chrome/109.0')

    assert.equal(api.browserSupport('Edge/18.19041').supported, false)
    assert.equal(api.browserSupport('Trident/7.0; rv:11.0').supported, false)
  })
})
