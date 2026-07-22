// Samples the actual pixels of src/img/siorik_logo.png and reports the
// dominant colors found, so brand tokens are picked from measured hex
// values rather than eyeballed from a screenshot.
//
// Run with: node scripts/extract-brand-colors.mjs
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Jimp } from 'jimp'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const imagePath = path.resolve(__dirname, '../src/img/siorik_logo.png')

// Bucket size per RGB channel — anti-aliased edges produce thousands of
// near-duplicate colors, so nearby shades are grouped together before
// ranking by frequency. The reported hex is the average of the actual
// pixels in each bucket, not the bucket's quantized corner.
const QUANT = 16

function toHex(r, g, b) {
  return (
    '#' +
    [r, g, b]
      .map((v) => Math.round(v).toString(16).padStart(2, '0'))
      .join('')
  )
}

function isNearWhite({ r, g, b }) {
  return r > 235 && g > 235 && b > 235
}

async function main() {
  const image = await Jimp.read(imagePath)
  const { width, height, data } = image.bitmap

  const buckets = new Map()

  image.scan(0, 0, width, height, (_x, _y, idx) => {
    const r = data[idx + 0]
    const g = data[idx + 1]
    const b = data[idx + 2]
    const a = data[idx + 3]
    if (a < 16) return // fully transparent pixel, not part of the visible mark

    const key = [Math.floor(r / QUANT), Math.floor(g / QUANT), Math.floor(b / QUANT)].join(',')
    const bucket = buckets.get(key) ?? { r: 0, g: 0, b: 0, count: 0 }
    bucket.r += r
    bucket.g += g
    bucket.b += b
    bucket.count += 1
    buckets.set(key, bucket)
  })

  const totalPixels = width * height
  const results = [...buckets.values()]
    .map((bucket) => {
      const r = bucket.r / bucket.count
      const g = bucket.g / bucket.count
      const b = bucket.b / bucket.count
      return {
        hex: toHex(r, g, b),
        r: Math.round(r),
        g: Math.round(g),
        b: Math.round(b),
        count: bucket.count,
        percent: (bucket.count / totalPixels) * 100,
      }
    })
    .sort((a, b) => b.count - a.count)

  console.log(`Analyzed ${imagePath}`)
  console.log(`Image size: ${width}x${height} (${totalPixels} pixels)\n`)

  console.log('Top dominant colors (all pixels, including background):')
  for (const c of results.slice(0, 15)) {
    console.log(`  ${c.hex}   rgb(${c.r}, ${c.g}, ${c.b})   ${c.percent.toFixed(2)}%`)
  }

  console.log('\nDominant colors excluding near-white background (candidate brand/ink colors):')
  const inkColors = results.filter((c) => !isNearWhite(c))
  for (const c of inkColors.slice(0, 15)) {
    console.log(`  ${c.hex}   rgb(${c.r}, ${c.g}, ${c.b})   ${c.percent.toFixed(2)}%`)
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
})
