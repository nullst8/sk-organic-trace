export type ParticipantRole = 'producer' | 'handler' | 'retailer' | 'regulator'
export type EventType = 'harvest' | 'handoff' | 'process' | 'ship' | 'retail'

export interface Participant {
  id: string
  name: string
  role: ParticipantRole
  public_key: string
  created_at: string
}

export interface EventRow {
  id: string
  batch_id: string
  event_type: EventType
  actor_id: string
  payload_json: string
  prev_hash: string
  hash: string
  signature: string
  seq: number
  created_at: string
}

export interface Batch {
  id: string
  product_name: string
  origin: string
  organic_claim: boolean
  producer_id: string
  created_at: string
  events: EventRow[]
}

export interface VerifyResult {
  batch_id: string
  intact: boolean
  event_count: number
  broken_at_seq: number | null
  message: string
}

export interface Anchor {
  id: number
  merkle_root: string
  from_seq: number
  to_seq: number
  tx_hash: string | null
  dry_run: boolean
  anchored_at: string
  explorer_url?: string | null
}

export interface ChainStatus {
  mode: string
  contract?: string | null
  chain_id?: number | null
  funding_address?: string | null
  balance_eth?: number | null
  explorer_contract?: string | null
  explorer_address?: string | null
  note?: string
  faucet_urls?: string[]
}

export interface Health {
  status: string
  service: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? JSON.stringify(body)
    } catch {
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/api/health'),
  listParticipants: () => request<Participant[]>('/api/participants'),
  createParticipant: (name: string, role: ParticipantRole) =>
    request<Participant>('/api/participants', {
      method: 'POST',
      body: JSON.stringify({ name, role }),
    }),
  listBatches: () => request<Batch[]>('/api/batches'),
  getBatch: (id: string) => request<Batch>(`/api/batches/${id}`),
  createBatch: (body: {
    product_name: string
    origin: string
    organic_claim: boolean
    producer_id: string
    harvest_note?: string
  }) =>
    request<Batch>('/api/batches', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  addEvent: (
    batchId: string,
    body: { event_type: EventType; actor_id: string; details?: Record<string, unknown> },
  ) =>
    request<EventRow>(`/api/batches/${batchId}/events`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  verify: (batchId: string) => request<VerifyResult>(`/api/batches/${batchId}/verify`),
  qrUrl: (batchId: string) => `/api/batches/${batchId}/qr`,
  listAnchors: () => request<Anchor[]>('/api/anchors'),
  createAnchor: () => request<Anchor>('/api/anchors', { method: 'POST' }),
  chainStatus: () => request<ChainStatus>('/api/chain/status'),
}
