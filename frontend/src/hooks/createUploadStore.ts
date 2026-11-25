/**
 * A small upload queue for single-file accounting tools (audit threshold,
 * FDIC exposure): files are POSTed two at a time and each result is kept.
 *
 * Each store is module-level, so results survive switching tabs within
 * Accounting tools. A page refresh clears them.
 */
import { useSyncExternalStore } from 'react'
import axios from 'axios'
import apiClient from '../api/client'

export type UploadStatus = 'queued' | 'running' | 'done' | 'error'

export interface UploadItem<T> {
  id: string
  name: string
  status: UploadStatus
  result: T | null
  error: string | null
  file: File | null
}

export interface UploadStore<T> {
  add: (files: File[]) => { rejected: string[] }
  retry: (id: string) => void
  remove: (id: string) => void
  clear: () => void
  useItems: () => UploadItem<T>[]
  /** test hook */
  _reset: () => void
}

const CONCURRENCY = 2

export function createUploadStore<T>(opts: {
  url: string
  field: string
  /** lower-case extensions accepted, e.g. ['.pdf'] */
  accept: string[]
  timeoutMs?: number
}): UploadStore<T> {
  let items: UploadItem<T>[] = []
  const listeners = new Set<() => void>()
  let nextId = 1

  const set = (next: UploadItem<T>[]) => {
    items = next
    listeners.forEach((l) => l())
  }
  const update = (id: string, patch: Partial<UploadItem<T>>) =>
    set(items.map((x) => (x.id === id ? { ...x, ...patch } : x)))

  async function run(item: UploadItem<T>) {
    update(item.id, { status: 'running', error: null })
    const form = new FormData()
    form.append(opts.field, item.file as File)
    try {
      const res = await apiClient.post<T>(opts.url, form, { timeout: opts.timeoutMs ?? 120_000 })
      update(item.id, { status: 'done', result: res.data, file: null })
    } catch (e) {
      const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
      update(item.id, {
        status: 'error',
        error: typeof detail === 'string' ? detail : 'Could not process this file.',
      })
    }
    pump()
  }

  function pump() {
    const running = items.filter((x) => x.status === 'running').length
    items
      .filter((x) => x.status === 'queued')
      .slice(0, Math.max(0, CONCURRENCY - running))
      .forEach((x) => void run(x))
  }

  return {
    add(files) {
      const rejected: string[] = []
      const added: UploadItem<T>[] = []
      for (const file of files) {
        const name = file.name.toLowerCase()
        if (!opts.accept.some((ext) => name.endsWith(ext))) {
          rejected.push(file.name)
          continue
        }
        added.push({
          id: String(nextId++),
          name: file.name,
          status: 'queued',
          result: null,
          error: null,
          file,
        })
      }
      if (added.length) {
        set([...items, ...added])
        pump()
      }
      return { rejected }
    },
    retry(id) {
      const x = items.find((i) => i.id === id)
      if (x?.status === 'error' && x.file) {
        update(id, { status: 'queued', error: null })
        pump()
      }
    },
    remove(id) {
      set(items.filter((x) => x.id !== id || x.status === 'running'))
    },
    clear() {
      set(items.filter((x) => x.status === 'running'))
    },
    useItems() {
      return useSyncExternalStore(
        (l) => {
          listeners.add(l)
          return () => listeners.delete(l)
        },
        () => items,
      )
    },
    _reset() {
      items = []
      nextId = 1
    },
  }
}
