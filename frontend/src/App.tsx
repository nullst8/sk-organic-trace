import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  api,
  type Anchor,
  type Batch,
  type ChainStatus,
  type EventType,
  type Participant,
  type ParticipantRole,
  type VerifyResult,
} from './api'
import { QrScanner } from './QrScanner'
import './App.css'

type Page = 'home' | 'producer' | 'handler' | 'consumer' | 'admin'

function App() {
  const [page, setPage] = useState<Page>('home')
  const [health, setHealth] = useState<string>('checking…')
  const [chain, setChain] = useState<ChainStatus | null>(null)
  const [participants, setParticipants] = useState<Participant[]>([])
  const [batches, setBatches] = useState<Batch[]>([])
  const [error, setError] = useState<string | null>(null)
  const [traceId, setTraceId] = useState(() => {
    const m = window.location.pathname.match(/^\/trace\/([^/]+)/)
    return m?.[1] ?? ''
  })

  const producers = useMemo(
    () => participants.filter((p) => p.role === 'producer'),
    [participants],
  )
  const handlers = useMemo(
    () => participants.filter((p) => p.role !== 'producer'),
    [participants],
  )

  async function refresh() {
    const [p, b] = await Promise.all([api.listParticipants(), api.listBatches()])
    setParticipants(p)
    setBatches(b)
  }

  useEffect(() => {
    api
      .health()
      .then((h) => setHealth(`${h.status} · ${h.service}`))
      .catch(() => setHealth('backend unreachable'))
    api.chainStatus().then(setChain).catch(() => setChain(null))
    refresh().catch((e) => setError(String(e.message ?? e)))
    if (traceId) setPage('consumer')
  }, [])

  return (
    <div className="shell">
      <header className="top">
        <button type="button" className="brand" onClick={() => setPage('home')}>
          Sikkim Organic Trace
        </button>
        <nav>
          <button
            type="button"
            className={page === 'producer' ? 'nav-btn active' : 'nav-btn'}
            onClick={() => setPage('producer')}
          >
            Producer
          </button>
          <button
            type="button"
            className={page === 'handler' ? 'nav-btn active' : 'nav-btn'}
            onClick={() => setPage('handler')}
          >
            Handler
          </button>
          <button
            type="button"
            className={page === 'consumer' ? 'nav-btn active' : 'nav-btn'}
            onClick={() => setPage('consumer')}
          >
            Scan / Trace
          </button>
          <button
            type="button"
            className={page === 'admin' ? 'nav-btn active' : 'nav-btn'}
            onClick={() => setPage('admin')}
          >
            Admin
          </button>
        </nav>
        <p className="health">API: {health}</p>
      </header>

      {error && <p className="banner error">{error}</p>}
      {chain && (
        <p className="banner chain">
          Chain: <strong>{chain.mode}</strong>
          {chain.contract ? (
            <>
              {' '}
              · contract <code>{chain.contract.slice(0, 10)}…</code>
              {chain.explorer_contract && (
                <>
                  {' '}
                  <a href={chain.explorer_contract} target="_blank" rel="noreferrer">
                    explorer
                  </a>
                </>
              )}
            </>
          ) : (
            <>
              {' '}
              · fund <code>{chain.funding_address?.slice(0, 10)}…</code> then{' '}
              <code>python deploy_anchor.py</code>
            </>
          )}
        </p>
      )}

      <main>
        {page === 'home' && (
          <Home
            onProducer={() => setPage('producer')}
            onConsumer={() => setPage('consumer')}
          />
        )}
        {page === 'producer' && (
          <ProducerPage
            producers={producers}
            batches={batches}
            onError={setError}
            onRefresh={refresh}
          />
        )}
        {page === 'handler' && (
          <HandlerPage
            handlers={handlers.length ? handlers : participants}
            batches={batches}
            onError={setError}
            onRefresh={refresh}
          />
        )}
        {page === 'consumer' && (
          <ConsumerPage
            initialId={traceId}
            onError={setError}
            onIdChange={setTraceId}
          />
        )}
        {page === 'admin' && <AdminPage chain={chain} onError={setError} />}
      </main>
    </div>
  )
}

function Home({
  onProducer,
  onConsumer,
}: {
  onProducer: () => void
  onConsumer: () => void
}) {
  return (
    <section className="hero-block">
      <p className="eyebrow">Sikkim · farm to fork</p>
      <h1>Sikkim Organic Trace</h1>
      <p className="lede">
        Register organic batches, sign each handoff, and let anyone verify the
        chain with a QR scan — no wallet required.
      </p>
      <div className="actions">
        <button type="button" className="btn primary" onClick={onProducer}>
          Register a batch
        </button>
        <button type="button" className="btn ghost" onClick={onConsumer}>
          Trace a product
        </button>
      </div>
    </section>
  )
}

function ProducerPage({
  producers,
  batches,
  onError,
  onRefresh,
}: {
  producers: Participant[]
  batches: Batch[]
  onError: (e: string | null) => void
  onRefresh: () => Promise<void>
}) {
  const [name, setName] = useState('')
  const [product, setProduct] = useState('Large Cardamom')
  const [origin, setOrigin] = useState('Gangtok, Sikkim')
  const [producerId, setProducerId] = useState('')
  const [created, setCreated] = useState<Batch | null>(null)

  useEffect(() => {
    if (producers[0] && !producerId) setProducerId(producers[0].id)
  }, [producers, producerId])

  async function registerProducer(e: FormEvent) {
    e.preventDefault()
    onError(null)
    try {
      const p = await api.createParticipant(name, 'producer')
      setName('')
      await onRefresh()
      setProducerId(p.id)
    } catch (err) {
      onError(String((err as Error).message))
    }
  }

  async function createBatch(e: FormEvent) {
    e.preventDefault()
    onError(null)
    try {
      const b = await api.createBatch({
        product_name: product,
        origin,
        organic_claim: true,
        producer_id: producerId,
      })
      setCreated(b)
      await onRefresh()
    } catch (err) {
      onError(String((err as Error).message))
    }
  }

  return (
    <div className="grid two">
      <section className="panel">
        <h2>Register producer</h2>
        <form onSubmit={registerProducer} className="stack">
          <label>
            Farm / co-op name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <button type="submit" className="btn primary">
            Create producer
          </button>
        </form>
      </section>

      <section className="panel">
        <h2>Create batch</h2>
        <form onSubmit={createBatch} className="stack">
          <label>
            Producer
            <select
              value={producerId}
              onChange={(e) => setProducerId(e.target.value)}
              required
            >
              <option value="">Select…</option>
              {producers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Product
            <input value={product} onChange={(e) => setProduct(e.target.value)} required />
          </label>
          <label>
            Origin
            <input value={origin} onChange={(e) => setOrigin(e.target.value)} required />
          </label>
          <button type="submit" className="btn primary" disabled={!producerId}>
            Create + harvest event
          </button>
        </form>
      </section>

      {created && (
        <section className="panel span2">
          <h2>Batch ready</h2>
          <p>
            ID: <code>{created.id}</code>
          </p>
          <img
            className="qr"
            src={api.qrUrl(created.id)}
            alt="Batch QR"
            width={180}
            height={180}
          />
          <p>Print this QR on the packet. Path encoded: /trace/{created.id}</p>
        </section>
      )}

      <section className="panel span2">
        <h2>Recent batches</h2>
        <ul className="list">
          {batches.map((b) => (
            <li key={b.id}>
              <strong>{b.product_name}</strong> · {b.origin}
              <br />
              <code>{b.id}</code>
            </li>
          ))}
          {!batches.length && <li>No batches yet.</li>}
        </ul>
      </section>
    </div>
  )
}

function HandlerPage({
  handlers,
  batches,
  onError,
  onRefresh,
}: {
  handlers: Participant[]
  batches: Batch[]
  onError: (e: string | null) => void
  onRefresh: () => Promise<void>
}) {
  const [handlerName, setHandlerName] = useState('')
  const [handlerRole, setHandlerRole] = useState<ParticipantRole>('handler')
  const [batchId, setBatchId] = useState('')
  const [actorId, setActorId] = useState('')
  const [eventType, setEventType] = useState<EventType>('handoff')
  const [note, setNote] = useState('')

  useEffect(() => {
    if (handlers[0] && !actorId) setActorId(handlers[0].id)
    if (batches[0] && !batchId) setBatchId(batches[0].id)
  }, [handlers, batches, actorId, batchId])

  async function registerHandler(e: FormEvent) {
    e.preventDefault()
    onError(null)
    try {
      const p = await api.createParticipant(handlerName, handlerRole)
      setHandlerName('')
      await onRefresh()
      setActorId(p.id)
    } catch (err) {
      onError(String((err as Error).message))
    }
  }

  async function addEvent(e: FormEvent) {
    e.preventDefault()
    onError(null)
    try {
      await api.addEvent(batchId, {
        event_type: eventType,
        actor_id: actorId,
        details: note ? { note } : {},
      })
      setNote('')
      await onRefresh()
    } catch (err) {
      onError(String((err as Error).message))
    }
  }

  return (
    <div className="grid two">
      <section className="panel">
        <h2>Register participant</h2>
        <form onSubmit={registerHandler} className="stack">
          <label>
            Company name
            <input
              value={handlerName}
              onChange={(e) => setHandlerName(e.target.value)}
              required
            />
          </label>
          <label>
            Role
            <select
              value={handlerRole}
              onChange={(e) => setHandlerRole(e.target.value as ParticipantRole)}
            >
              <option value="handler">handler</option>
              <option value="retailer">retailer</option>
              <option value="regulator">regulator</option>
            </select>
          </label>
          <button type="submit" className="btn primary">
            Create participant
          </button>
        </form>
      </section>

      <section className="panel">
        <h2>Append handoff event</h2>
        <form onSubmit={addEvent} className="stack">
          <label>
            Batch
            <select value={batchId} onChange={(e) => setBatchId(e.target.value)} required>
              <option value="">Select…</option>
              {batches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.product_name} ({b.id.slice(0, 8)}…)
                </option>
              ))}
            </select>
          </label>
          <label>
            Actor
            <select value={actorId} onChange={(e) => setActorId(e.target.value)} required>
              <option value="">Select…</option>
              {handlers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.role})
                </option>
              ))}
            </select>
          </label>
          <label>
            Event type
            <select
              value={eventType}
              onChange={(e) => setEventType(e.target.value as EventType)}
            >
              <option value="handoff">handoff</option>
              <option value="process">process</option>
              <option value="ship">ship</option>
              <option value="retail">retail</option>
            </select>
          </label>
          <label>
            Note
            <input value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <button type="submit" className="btn primary" disabled={!batchId || !actorId}>
            Sign & append
          </button>
        </form>
      </section>
    </div>
  )
}

function ConsumerPage({
  initialId,
  onError,
  onIdChange,
}: {
  initialId: string
  onError: (e: string | null) => void
  onIdChange: (id: string) => void
}) {
  const [id, setId] = useState(initialId)
  const [batch, setBatch] = useState<Batch | null>(null)
  const [verify, setVerify] = useState<VerifyResult | null>(null)
  const [anchor, setAnchor] = useState<Anchor | null>(null)
  const [scanError, setScanError] = useState('')

  async function load(batchId: string) {
    onError(null)
    try {
      const [b, v, anchors] = await Promise.all([
        api.getBatch(batchId),
        api.verify(batchId),
        api.listAnchors(),
      ])
      setBatch(b)
      setVerify(v)
      setAnchor(anchors[0] ?? null)
      setId(batchId)
      onIdChange(batchId)
      window.history.replaceState(null, '', `/trace/${batchId}`)
    } catch (err) {
      setBatch(null)
      setVerify(null)
      setAnchor(null)
      onError(String((err as Error).message))
    }
  }

  useEffect(() => {
    if (initialId) load(initialId)
  }, [])

  return (
    <section className="panel stack">
      <h2>Trace a product</h2>
      <QrScanner
        onScan={(batchId) => {
          setScanError('')
          load(batchId)
        }}
        onError={(message) => {
          if (message) setScanError(message)
        }}
      />
      {scanError && <p className="banner error">{scanError}</p>}
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault()
          load(id.trim())
        }}
      >
        <input
          className="grow"
          placeholder="Paste batch UUID"
          value={id}
          onChange={(e) => setId(e.target.value)}
        />
        <button type="submit" className="btn primary">
          Verify
        </button>
      </form>
      <p className="muted">
        Scan a packet QR, or paste a batch UUID. QR payload is{' '}
        <code>/trace/&lt;batch-id&gt;</code>.
      </p>

      {verify && (
        <p className={verify.intact ? 'badge ok' : 'badge bad'}>
          {verify.intact ? 'Chain intact' : 'Tampered'} — {verify.message}
        </p>
      )}

      {anchor && (
        <p className="muted">
          Latest on-chain anchor: <code>{anchor.merkle_root.slice(0, 18)}…</code>
          {anchor.tx_hash && (
            <>
              {' '}
              · tx <code>{anchor.tx_hash.slice(0, 18)}…</code>
              {anchor.dry_run ? ' (dry-run)' : ' (mined)'}
              {anchor.explorer_url && (
                <>
                  {' '}
                  <a href={anchor.explorer_url} target="_blank" rel="noreferrer">
                    view on explorer
                  </a>
                </>
              )}
            </>
          )}
        </p>
      )}

      {batch && (
        <>
          <h3>
            {batch.product_name}{' '}
            {batch.organic_claim && <span className="tag">organic claim</span>}
          </h3>
          <p>
            Origin: {batch.origin}
            <br />
            <code>{batch.id}</code>
          </p>
          <ol className="timeline">
            {batch.events.map((ev) => (
              <li key={ev.id}>
                <strong>
                  #{ev.seq} {ev.event_type}
                </strong>
                <br />
                <span className="muted">{new Date(ev.created_at).toLocaleString()}</span>
                <br />
                <code className="hash">{ev.hash.slice(0, 16)}…</code>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  )
}

function AdminPage({
  chain,
  onError,
}: {
  chain: ChainStatus | null
  onError: (e: string | null) => void
}) {
  const [anchors, setAnchors] = useState<Anchor[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function refreshAnchors() {
    try {
      setAnchors(await api.listAnchors())
    } catch (err) {
      onError(String((err as Error).message))
    }
  }

  useEffect(() => {
    refreshAnchors()
  }, [])

  async function anchorNow() {
    setBusy(true)
    setMessage(null)
    onError(null)
    try {
      const a = await api.createAnchor()
      setMessage(
        `Anchored root ${a.merkle_root.slice(0, 16)}… covering seq ${a.from_seq}–${a.to_seq}` +
          (a.tx_hash ? ` · tx ${a.tx_hash.slice(0, 16)}… ${a.dry_run ? '(dry-run)' : '(mined)'}` : ''),
      )
      await refreshAnchors()
    } catch (err) {
      onError(String((err as Error).message))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid two">
      <section className="panel">
        <h2>Anchor to chain</h2>
        <p className="muted">
          Compress all unanchored event hashes into a Merkle root and publish it to
          the anchor contract.
        </p>
        <dl className="kv">
          <dt>Mode</dt>
          <dd>{chain?.mode ?? 'unknown'}</dd>
          {chain?.contract && (
            <>
              <dt>Contract</dt>
              <dd>
                <code>{chain.contract}</code>
              </dd>
            </>
          )}
          {chain?.funding_address && (
            <>
              <dt>Wallet</dt>
              <dd>
                <code>{chain.funding_address}</code>
                {typeof chain.balance_eth === 'number' && (
                  <span className="muted"> · {chain.balance_eth} ETH</span>
                )}
              </dd>
            </>
          )}
        </dl>
        {chain?.faucet_urls && chain.faucet_urls.length > 0 && (
          <p className="muted">
            Fund the wallet on Sepolia to anchor publicly:{' '}
            {chain.faucet_urls.map((u, i) => (
              <span key={u}>
                {i > 0 && ' · '}
                <a href={u} target="_blank" rel="noreferrer">
                  faucet {i + 1}
                </a>
              </span>
            ))}
          </p>
        )}
        <div className="actions">
          <button type="button" className="btn primary" onClick={anchorNow} disabled={busy}>
            {busy ? 'Anchoring…' : 'Anchor latest events'}
          </button>
        </div>
        {message && <p className="banner chain">{message}</p>}
      </section>

      <section className="panel">
        <h2>Anchors</h2>
        {!anchors.length && <p className="muted">No anchors yet. Add events, then anchor.</p>}
        <ul className="list">
          {anchors.map((a) => (
            <li key={a.id}>
              <strong>#{a.id}</strong> · seq {a.from_seq}–{a.to_seq}{' '}
              <span className="tag">{a.dry_run ? 'dry-run' : 'on-chain'}</span>
              <br />
              <code className="hash">{a.merkle_root}</code>
              {a.tx_hash && (
                <>
                  <br />
                  tx <code className="hash">{a.tx_hash}</code>
                  {a.explorer_url && (
                    <>
                      {' '}
                      <a href={a.explorer_url} target="_blank" rel="noreferrer">
                        view on explorer
                      </a>
                    </>
                  )}
                </>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

export default App
