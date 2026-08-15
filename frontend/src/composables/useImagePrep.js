/**
 * Prepare a photo for the receipt scanner, in the browser.
 *
 * Phone cameras produce 4-12 MB images; the API takes 4 MB and bills by pixel
 * area. Downscaling here keeps uploads fast and cost predictable, while staying
 * high enough that small print stays legible.
 */

const MAX_EDGE = 1800 // px on the long edge — comfortably legible for receipts
const TARGET_BYTES = 3.5 * 1024 * 1024

export function isImage(file) {
  return Boolean(file) && /^image\/(jpeg|png|webp|gif)$/i.test(file.type)
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      resolve(img)
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('That file could not be read as an image'))
    }
    img.src = url
  })
}

function toBlob(canvas, quality) {
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
}

/** Returns { file, previewUrl, width, height, bytes }. */
export async function prepareReceiptImage(file) {
  if (!isImage(file)) {
    throw new Error('Please choose a photo (JPEG, PNG, WebP or GIF)')
  }

  const img = await loadImage(file)
  const scale = Math.min(1, MAX_EDGE / Math.max(img.width, img.height))
  const width = Math.round(img.width * scale)
  const height = Math.round(img.height * scale)

  // Small enough already, and not a format worth re-encoding.
  if (scale === 1 && file.size <= TARGET_BYTES) {
    return {
      file,
      previewUrl: URL.createObjectURL(file),
      width: img.width,
      height: img.height,
      bytes: file.size,
    }
  }

  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(img, 0, 0, width, height)

  let quality = 0.85
  let blob = await toBlob(canvas, quality)
  // Step the quality down rather than the resolution — legibility matters more.
  while (blob && blob.size > TARGET_BYTES && quality > 0.5) {
    quality -= 0.1
    blob = await toBlob(canvas, quality)
  }
  if (!blob) throw new Error('Could not process that image')

  const prepared = new File([blob], 'receipt.jpg', { type: 'image/jpeg' })
  return {
    file: prepared,
    previewUrl: URL.createObjectURL(prepared),
    width,
    height,
    bytes: prepared.size,
  }
}
