import { useEffect, useRef, useState } from 'react'

/**
 * Poll an async resource on an interval until a stop condition is met.
 *
 * Polling is driven by `key`: pass a value (e.g. a job id) to start, or `null`
 * to stay idle / stop. Uses a recursive `setTimeout` rather than `setInterval`
 * so a slow request can't overlap the next one. Automatically stops when
 * `shouldStop(data)` returns true and cancels on unmount or when `key` changes.
 */
export function usePolling<T>(
  key: string | null,
  fetcher: (key: string) => Promise<T>,
  shouldStop: (data: T) => boolean,
  intervalMs = 2000,
): { data: T | null; error: string | null } {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Keep the latest callbacks without restarting the loop each render.
  const fetcherRef = useRef(fetcher)
  const shouldStopRef = useRef(shouldStop)
  useEffect(() => {
    fetcherRef.current = fetcher
    shouldStopRef.current = shouldStop
  })

  useEffect(() => {
    if (!key) return

    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    const tick = async () => {
      try {
        const result = await fetcherRef.current(key)
        if (cancelled) return
        setData(result)
        if (shouldStopRef.current(result)) return
      } catch {
        if (cancelled) return
        setError('Polling failed.')
        return
      }
      timer = setTimeout(tick, intervalMs)
    }

    tick()

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [key, intervalMs])

  return { data, error }
}
