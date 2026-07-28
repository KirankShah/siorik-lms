// The source logo (src/img/siorik_logo.png) is a 1254x1254 PNG at 1.3MB —
// far larger than any on-screen use needs (a ~40px nav/lockup icon, or a
// blurred low-opacity watermark). This generates right-sized derivatives so
// the login page and nav header don't ship a multi-hundred-KB image for a
// small icon.
//
// Run with: node scripts/generate-logo-assets.mjs
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Jimp } from 'jimp'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(__dirname, '../src/img/siorik_logo.png')

const OUTPUTS = [
  { suffix: 'icon', width: 128 }, // nav header + login lockup icon
  { suffix: '320', width: 320 }, // login panel watermark (rendered large, blurred, low-opacity — a small source is imperceptible there)
]

async function main() {
  const source = await Jimp.read(sourcePath)
  for (const { suffix, width } of OUTPUTS) {
    const outPath = path.resolve(__dirname, `../src/img/siorik_logo_${suffix}.png`)
    await source.clone().resize({ w: width }).write(outPath)
    console.log(`wrote ${outPath}`)
  }
}

main().catch((err) => {
  console.error(err)
  process.exitCode = 1
})
