/**
 * Financial review session: a queue of packet PDFs checked against
 * POST /api/financials/check.
 *
 * Lives in a module-level store (not component state) so a session keeps
 * running while the user visits other pages. It is not persisted: a page
 * refresh starts a new session.
 *
 * Packets are checked without screenshots (~7 KB per result instead of
 * ~1.5 MB). When a packet is opened, its screenshots are rendered from the
 * same File via POST /api/financials/evidence and kept for the few most
 * recently opened packets only, so a session of 180 packets stays light.
 */
import { useSyncExternalStore } from 'react'
import axios from 'axios'
import apiClient from '../api/client'
import type { FinancialCheckReport } from '../types'

export type PacketStatus = 'queued' | 'checking' | 'done' | 'error'

export interface PacketEvidence {
  status: 'loading' | 'done' | 'error'
  /** keyed by evidenceKey(checkId, side) */
  images: Record<string, string | null>
}

export interface SessionPacket {
  id: string
  name: string
  status: PacketStatus
  report: FinancialCheckReport | null
  error: string | null
  /** The selected file. Browsers read a File from disk on demand, so keeping
   * it costs little; it's needed to retry and to render screenshots later. */
  file: File | null
  evidence: PacketEvidence | null
}

// Production runs 2 gunicorn workers; more parallel requests just queue there.
const CONCURRENCY = 2
// Screenshots are ~1.5 MB per packet; keep only the most recently opened.
const EVIDENCE_CACHE = 3

let packets: SessionPacket[] = []
const listeners = new Set<() => void>()
let nextId = 1
let evidenceOrder: string[] = [] // packet ids, most recently opened last

export function evidenceKey(checkId: string, side: 'left' | 'right'): string {
  return `${checkId}:${side}`
}

function set(next: SessionPacket[]) {
  packets = next
  listeners.forEach((l) => l())
}

function update(id: string, patch: Partial<SessionPacket>) {
  set(packets.map((p) => (p.id === id ? { ...p, ...patch } : p)))
}

function errorText(e: unknown, fallback: string): string {
  const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
  return typeof detail === 'string' ? detail : fallback
}

async function check(p: SessionPacket) {
  update(p.id, { status: 'checking', error: null })
  const form = new FormData()
  form.append('financial_report', p.file as File)
  form.append('images', 'false')
  try {
    // Scanned packets are several MB and take a few seconds to read.
    const res = await apiClient.post<FinancialCheckReport>('/api/financials/check', form, {
      timeout: 120_000,
    })
    update(p.id, { status: 'done', report: res.data })
  } catch (e) {
    update(p.id, { status: 'error', error: errorText(e, 'Could not check this packet.') })
  }
  pump()
}

function pump() {
  const running = packets.filter((p) => p.status === 'checking').length
  const queued = packets.filter((p) => p.status === 'queued')
  queued.slice(0, Math.max(0, CONCURRENCY - running)).forEach((p) => void check(p))
}

/** Fetch a finished packet's screenshots (no-op if cached or in flight). */
export async function loadEvidence(id: string) {
  const p = packets.find((x) => x.id === id)
  if (!p?.report || !p.file) return
  evidenceOrder = [...evidenceOrder.filter((x) => x !== id), id]
  if (p.evidence && p.evidence.status !== 'error') return

  // Evict screenshots of packets opened longest ago.
  const evict = new Set(evidenceOrder.slice(0, -EVIDENCE_CACHE))
  evidenceOrder = evidenceOrder.slice(-EVIDENCE_CACHE)
  if (evict.size) {
    set(packets.map((x) => (evict.has(x.id) ? { ...x, evidence: null } : x)))
  }

  const keys: string[] = []
  const regions: { page: number; bbox: number[] }[] = []
  for (const c of p.report.checks) {
    for (const side of ['left', 'right'] as const) {
      const s = c[side]
      if (s?.page && s.bbox && !s.image) {
        keys.push(evidenceKey(c.id, side))
        regions.push({ page: s.page, bbox: s.bbox })
      }
    }
  }
  if (!regions.length) {
    update(id, { evidence: { status: 'done', images: {} } })
    return
  }

  update(id, { evidence: { status: 'loading', images: {} } })
  const form = new FormData()
  form.append('financial_report', p.file)
  form.append('regions', JSON.stringify(regions))
  try {
    const res = await apiClient.post<{ images: (string | null)[] }>(
      '/api/financials/evidence',
      form,
      { timeout: 120_000 },
    )
    const images: Record<string, string | null> = {}
    keys.forEach((k, i) => (images[k] = res.data.images[i] ?? null))
    // Only store if this packet is still in the cache window.
    if (evidenceOrder.includes(id)) update(id, { evidence: { status: 'done', images } })
  } catch {
    update(id, { evidence: { status: 'error', images: {} } })
  }
}

export function addPackets(files: File[]): { rejected: string[] } {
  const rejected: string[] = []
  const added: SessionPacket[] = []
  for (const file of files) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      rejected.push(file.name)
      continue
    }
    added.push({
      id: String(nextId++),
      name: file.name,
      status: 'queued',
      report: null,
      error: null,
      file,
      evidence: null,
    })
  }
  if (added.length) {
    set([...packets, ...added])
    pump()
  }
  return { rejected }
}

export function retryPacket(id: string) {
  const p = packets.find((x) => x.id === id)
  if (p?.status === 'error' && p.file) {
    update(id, { status: 'queued', error: null })
    pump()
  }
}

export function removePacket(id: string) {
  evidenceOrder = evidenceOrder.filter((x) => x !== id)
  set(packets.filter((p) => p.id !== id || p.status === 'checking'))
}

/** Clears finished and queued packets; ones mid-check finish and stay. */
export function clearSession() {
  evidenceOrder = []
  set(packets.filter((p) => p.status === 'checking'))
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useReviewSession(): SessionPacket[] {
  return useSyncExternalStore(subscribe, () => packets)
}

/** Test hook: reset module state between tests. */
export function _resetSession() {
  packets = []
  nextId = 1
  evidenceOrder = []
}
