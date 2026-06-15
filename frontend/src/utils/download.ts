/**
 * Download a file from a (presigned) URL by fetching it as a blob and clicking a
 * synthetic anchor. Fetching the blob first (rather than navigating to the URL)
 * keeps the SPA loaded and lets us control the saved filename.
 */
export async function downloadFromUrl(url: string, filename: string): Promise<void> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error('Failed to download file.')
  }

  const blob = await response.blob()
  const blobUrl = window.URL.createObjectURL(blob)

  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()

  window.URL.revokeObjectURL(blobUrl)
}
