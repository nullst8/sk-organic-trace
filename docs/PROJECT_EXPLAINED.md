# Sikkim Organic Trace — Full Project Explainer

**A plain-English walkthrough for the presentation.**  
Written for a student who knows Python + React (a little rusty) and needs to understand and present this project without prior blockchain knowledge.

---

## Part 1 — What this project even is

**The problem:** Sikkim is India's first fully-organic state. People sell "Sikkim organic" cardamom, ginger, turmeric, etc. But how does a *buyer* know it's really from Sikkim and really organic? Paper records are easy to fake or "fix".

**The solution:** a web app where every step of a product's journey is recorded in a tamper-proof way, and a customer can scan a QR code to see the whole history and whether it's been messed with.

The flow:

1. A **farmer** registers a batch (e.g. "Large Cardamom from Dzongu") and gets a QR code.
2. Every time it changes hands — collected, dried, trucked, put on a shelf — someone records a **handoff** with a digital signature.
3. A **customer** scans the QR and sees the timeline + a green **"Chain intact"** badge.
4. If anyone edits a record (even directly in the database), the app detects it and shows **"Tampered"**.
5. Periodically, a single fingerprint of all recent events gets written to the *real Ethereum blockchain* (a test network), so there's an independent public proof that we can't silently rewrite history.

---

## Part 2 — The "magic" in plain English

You don't need to know blockchain. You need to understand **5 small ideas**. Everything in the code is just these.

### 1. Hashing = a fingerprint

`SHA-256` is a function that takes *any* text and returns a fixed **64-character** string of hex (0-9, a-f). Like a fingerprint:

- Same input → always the same hash.
- Change even one character → a *completely different* hash.

```
hash("hello") = 2cf24dba... (fixed 64 chars, always)
hash("Hello") = 5d41402a... (totally different)
```

You can't go backwards (can't recover "hello" from the hash). That's what makes it useful.

### 2. A hash chain = links that point to each other

Imagine a chain. Each new event records:

- the **fingerprint of the previous event** (`prev_hash`)
- its own data
- its **own fingerprint** = `hash(prev_hash + its_data)`

```
Event 1: prev = "0000...0" (genesis),  hash = H(0000 + data1)
Event 2: prev = hash1,                   hash = H(hash1 + data2)
Event 3: prev = hash2,                   hash = H(hash2 + data3)
```

Now if someone edits **Event 1's data**, its hash no longer matches what Event 2 recorded as `prev_hash`. The break is detectable. **This is the whole trick** — the "blockchain" in our project is basically this chain of hashes stored in a normal database.

### 3. Digital signatures = proof of "who"

Each participant (farmer, trucker) gets a **keypair**: a *private* key (secret, stays with them) and a *public* key (shown to everyone). With the private key they **sign** a message; with the public key anyone can **verify** that signature really came from them. This is called **Ed25519**. It proves an event was really created by that actor and hasn't been altered.

### 4. A Merkle tree = one fingerprint for many records

We have many events. Instead of storing all of them on Ethereum, we combine their hashes in pairs, hash the pairs, repeat, until we get **one** hash (the "Merkle root"). One number summarizes thousands of events. Change any single event → the root changes.

```
hashA  hashB  hashC  hashC   (odd -> duplicate last)
   \    /        \    /
    hashAB        hashCC
        \        /
         root
```

### 5. Anchoring = publishing that one fingerprint publicly

We take the Merkle root and write it to a **real blockchain** (Ethereum testnet called Sepolia) via a small program (the "smart contract" `ProvenanceAnchor.sol`). The blockchain is a public ledger nobody controls, so once the root is there, it can't be edited. Later, anyone can recompute our Merkle root and check it *matches* the one on Ethereum. If they differ → something was tampered.

**Honest framing (say this in your presentation):** The events live in *our* SQLite database (off-chain). We don't run a real blockchain for each event (that would be slow and expensive). Instead we publish a **checkpoint fingerprint** to Ethereum. It's the "off-chain data + on-chain integrity reference" pattern from the literature.

---

## Part 3 — The architecture (how files fit)

```
Browser (React)  --HTTP/JSON-->  FastAPI (Python)  -->  SQLite (events)
                                   | hash chain + signatures
                                   | builds Merkle root
                                   v
                            ProvenanceAnchor.sol  (on Ethereum Sepolia
                                                    or a fake in-memory chain)
```

The React app and Python app never share memory. React calls URLs like `/api/batches/...`, FastAPI answers with JSON. The `vite` dev server forwards those `/api` requests to Python (the "proxy") so the browser stays on one port.

---

## Part 4 — The backend files (Python)

Everything lives in `backend/app/`.

### `main.py` — the front door

`FastAPI()` creates the web app object. It's a framework (like Express in JS) — you write functions and attach them to URLs.

`app.add_middleware(CORSMiddleware, ...)` — CORS lets the browser on port 5173 talk to port 8000. (Mostly unneeded because of the Vite proxy, but there as backup.)

`app.include_router(router)` — the actual routes are defined in another file (`routers.py`); this line "plugs them in".

`@app.on_event("startup")` — a **decorator** (`@...`) wraps the function; here it tells FastAPI "run this once when the server starts". It creates the database tables if they don't exist yet.

### `database.py` — connects to SQLite

SQLite is a database that's just a single file (`provenance.db`). An "engine" is the object that talks to it.

`get_db()` is a **generator** (has `yield`). FastAPI uses it as "dependency injection" — every route that says `db: Session = Depends(get_db)` gets a fresh database connection handed to it, and it's automatically closed afterward.

### `models.py` — the tables (SQLAlchemy)

SQLAlchemy maps Python classes to database tables.

`class ParticipantRole(str, enum.Enum)` — an **enum** = a fixed set of allowed values (`producer`, `handler`, `retailer`, `regulator`).

`class Participant(Base):` with `__tablename__ = "participants"` defines a table. `Mapped[str]` is a **type hint** ("this column holds a string"). `mapped_column(...)` describes the column: `primary_key=True` (unique id), `default=_uuid` (auto-generate a random id).

There are **4 tables**:

- **Participant** — a person/company. Has name, role, public key, and (for demo convenience) a stored private key.
- **Batch** — a batch of product. Has product name, origin, organic claim, producer id.
- **Event** — one recorded step. Stores the hash-chain fields: `prev_hash`, `hash`, `signature`, plus a `seq` (sequence number) and the payload as JSON text.
- **Anchor** — one Merkle root published to Ethereum, remembering which events it covered and the transaction hash.

### `schemas.py` — request/response shapes (Pydantic)

Pydantic validates data. `BaseModel` = a data class with built-in checking.

`class ParticipantCreate(BaseModel)` with `name: str = Field(min_length=1, max_length=200)` says "when someone sends `POST /participants`, the JSON must have a `name` (1–200 chars) and a `role`". Wrong shape → FastAPI auto-rejects with a 422.

`model_config = {"from_attributes": True}` lets Pydantic read directly from a SQLAlchemy object and convert it to JSON.

### `crypto_chain.py` — the pure math (most important file to "get")

No database, no web — just the crypto building blocks.

- `canonical_json(obj)` — "canonical" = always produce the *same* string for the same data. `sort_keys=True` sorts dictionary keys so two people serializing the same data get identical strings (so hashes match).
- `sha256_hex(*parts)` — `*parts` = accept any number of arguments; hashes them all together, returns hex (idea #1).
- `generate_keypair()` — generates the public + private keypair (idea #3). `.hex()` turns raw bytes into readable hex.
- `sign_message(private_key, message)` / `verify_signature(public_key, message, signature)` — sign and verify. `verify_signature` returns `True`/`False`; it catches `InvalidSignature` (the try/except means "if verification fails, return False instead of crashing").
- `event_hash(prev_hash, payload, signature)` — the hash-chain formula (idea #2): `SHA256(prev + data + signature)`.
- `merkle_root(hashes)` — the Merkle tree (idea #4). Repeatedly pairs up hashes and combines them until one remains. `range(0, len(layer), 2)` counts by twos (0, 2, 4...) so each loop grabs a pair.

### `routers.py` — the actual endpoints (the "brain")

This is where URLs meet logic. `router = APIRouter(prefix="/api")` means every route starts with `/api`.

`@router.post("/participants", response_model=schemas.ParticipantOut)` with `body: schemas.ParticipantCreate` and `db: Session = Depends(get_db)`:
- `@router.post(...)` = "handle POST requests to `/api/participants`".
- `body:` = FastAPI parses + validates the incoming JSON.
- `db:` = hand me a database connection.
- `response_model=` = convert the return value into that shape.

`db.add(row)`, `db.commit()`, `db.refresh(row)` — add, actually write, then reload (so it has its auto-generated `id`).

**`create_batch`** checks the producer exists and has role `producer`, then creates the batch *and* its first event (`harvest`) using `_append_event`.

**`add_event`** rejects `harvest` (auto-created with the batch), then calls `_append_event`.

**`_append_event`** is the heart of the hash chain:

- `with _event_lock:` — a `threading.Lock()` that makes sure only one event is written at a time (so sequence numbers never clash).
- `prev_hash = last.hash if last else GENESIS_HASH` — previous event's hash, or 64 zeros ("genesis") for the first.
- `next_seq = (max(seq)) + 1` — a global sequence counter across all batches.
- Build the payload dict, serialize it canonically.
- `if signature:` verify it; `else:` server signs with the stored demo private key.
- `h = event_hash(prev_hash, payload, sig)` — then save the event.
- The `for _ in range(8): try/except IntegrityError` loop retries if two events race for the same `seq`.

**`verify_batch`** — the tamper detector (idea #2 applied). It *recomputes* everything from scratch and compares:

- check each signature is valid for its actor (else "Invalid signature at seq=...")
- check `expected == ev.hash` and `ev.prev_hash == prev` (else "Hash chain broken at seq=...")
- return "Chain intact" if everything matches.

**`create_anchor`** — the Merkle publish. `root = merkle_root([e.hash for e in events])` (a **list comprehension** = "a list of every event's hash"), then `submit_merkle_root(root)`, then save an Anchor row.

**`batch_qr`** — `payload = f"/trace/{batch_id}"` (an f-string inserts the id), then `qrcode.make(payload)` creates the QR image.

### `chain.py` — talks to Ethereum

- `CONTRACT_SOURCE` — the smart contract (the Ethereum program) embedded as a string (also duplicated in `contracts/`). A **smart contract** = a tiny program stored on the blockchain that anyone can call but nobody can alter.
- `_ensure_local_chain()` — if not connected to real Sepolia, spins up a **fake in-memory Ethereum** ("eth-tester") and deploys the contract there. This is why the banner says "local-eth-tester" — a sandbox Ethereum that still does real transactions, just not public.
- `submit_merkle_root(root)` — calls the contract's `anchor()` function: build a transaction → sign with private key → broadcast → wait for it to be "mined" (confirmed). Returns the transaction hash.
- `chain_status()` — reports what mode you're in (Sepolia vs local tester), your wallet address, balance, faucet links. This drives the warning banner.

### `settings.py` — reads config

`class Settings(BaseSettings)` — `BaseSettings` automatically reads these from the `.env` file. `str | None` = "a string or nothing" (modern Python for `Optional[str]`). `rpc_configured` is a `@property` — a computed value (looks like an attribute, actually a function). It's True only when RPC URL + private key + contract address are *all* set.

---

## Part 5 — The frontend files (React + TypeScript)

### `main.tsx` — entry point

`createRoot(document.getElementById('root')!).render(<App />)` boots React into the HTML `<div id="root">`. `!` is TypeScript's "I promise this isn't null" (non-null assertion).

### `api.ts` — all the HTTP calls in one place

`async function request<T>(path, init?)` — `<T>` is a **generic** ("works with any type, figure it out from context"). `async`/`await` = "wait for the network answer without freezing the page". `fetch` = the browser's built-in HTTP client. On a non-OK response it throws a readable error.

The `interface Participant {...}` blocks are TypeScript **types** — they describe the JSON shape so the editor catches typos.

`export const api = {...}` — a bag of ready-to-use functions (`api.health()`, `api.createParticipant()`, etc.). The whole app calls `api.xxx()` instead of writing `fetch` everywhere.

### `App.tsx` — all the screens

A single-page app (SPA). A `page` state variable decides which "page" shows:

- `const [page, setPage] = useState<Page>('home')` — `useState` is a React hook giving a value + a setter. Calling `setPage('producer')` re-renders.
- `useEffect(() => {...}, [])` — "run this after the component appears"; `[]` means "only once on load".
- `{page === 'home' && <Home />}` — JSX short-circuit: "if `page` is `'home'`, render `<Home/>`". JSX = the HTML-like syntax inside JS.

There are **5 screens** (components):

1. **Home** — hero text + two buttons.
2. **ProducerPage** — register a farm, create a batch, show its QR code.
3. **HandlerPage** — register a handler/retailer/regulator, append handoff events.
4. **ConsumerPage** — paste/scan a batch id, see timeline + "Chain intact"/"Tampered" badge + anchor info.
5. **AdminPage** — "Anchor latest events" button + list of anchors + chain/wallet details.

Common patterns:

- `e.preventDefault()` — stop the form from reloading the page.
- `try/catch` — error handling; `(err as Error)` = TypeScript "treat `err` as an Error type".
- `useMemo(() => ..., [deps])` — "recompute only when deps change" (a cache).
- In **ConsumerPage**, the deep-link trick: `window.location.pathname.match(/^\/trace\/([^/]+)/)` extracts the batch id from the URL, so scanning a QR on a phone opens directly to that batch. `m?.[1]` = optional chaining ("if `m` exists, give group 1"); `?? ''` = nullish coalescing ("or empty string if null").

### `QrScanner.tsx` — camera scanning

Uses the `html5-qrcode` library to access the camera. `extractBatchId(raw)` pulls the batch ID out of whatever the QR contained — either from `/trace/<uuid>` or a bare UUID. `useEffect`'s `return () => {...}` is the **cleanup** (stops the camera on unmount); `useRef` holds a reference to the scanner object without triggering re-renders.

### `vite.config.ts` — dev server + proxy

`proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } }` — any request to `/api/...` on the React server (port 5173) is silently forwarded to Python (port 8000). That's why the browser only ever talks to 5173. (Also why you got a 502 earlier — Python wasn't on 8000.)

### `package.json`

Lists dependencies (`react`, `react-dom`, `html5-qrcode`) and scripts (`dev`, `build`, `lint`). `packageManager: "pnpm@11.20.0"` means use **pnpm**, not npm.

---

## Part 6 — The contract + scripts

### `contracts/ProvenanceAnchor.sol` (Solidity)

```
mapping(uint256 => bytes32) public roots;   // dictionary: id -> root
uint256 public count;                       // how many anchors

function anchor(bytes32 root) external {    // anyone can call; store the root
    roots[count] = root;
    emit Anchored(count, root, block.timestamp);
    count++;
}
```

- `mapping(uint256 => bytes32)` = a dictionary mapping an id to a 32-byte root.
- `bytes32` = a 64-hex-char value, exactly our Merkle root size.
- `function anchor(bytes32 root) external` = "anyone can call this, pass a 32-byte root".
- `event Anchored(...)` + `emit Anchored(...)` = write a permanent, searchable log entry (visible on block explorers).
- `public` auto-generates a "getter" so anyone can read `roots[3]`.

That's the whole contract — it just *stores fingerprints*.

### `scripts/demo_flow.py` — your presentation script

This is **exactly what you should demo live**. It:

1. Registers a producer + handler.
2. Creates a cardamom batch, prints the QR + trace URL.
3. Adds handoff → process → ship → retail events.
4. Verifies → prints `intact=True` and the time taken.
5. Anchors the Merkle root.
6. **Corrupts one event directly in SQLite** and verifies again → `intact=False`, showing the exact broken link.

Run: `source .venv/bin/activate && python backend/scripts/demo_flow.py` (while the backend is running). The tamper step is your "wow" moment.

### `scripts/benchmark.py` — the numbers

Times how fast things are (create batch, write events, verify, anchor) and writes `docs/benchmarks.json` — e.g. "verify ~4.8 ms vs days for paper recall". Supports the "blockchain is faster than paper" claim.

### `deploy_anchor.py` — deploy the contract to Sepolia

Only needed for real (public) Ethereum. It funds/checks your wallet and deploys the contract, then writes its address into `.env`.

---

## Part 7 — The tests

- `tests/conftest.py` — shared setup. Creates a throwaway database so tests don't touch real data, plus a `TestClient` (a fake browser) to hit the API.
- `tests/test_crypto_chain.py` — checks the math: hashes are deterministic, signatures work, tampered signatures fail, Merkle roots behave.
- `tests/test_api.py` — checks the full API: create participant/batch/events, reject bad input, verify intact, and **detect tampering**.

Run: `source .venv/bin/activate && cd backend && python -m pytest tests/ -q` → `24 passed`.

---

## Part 8 — Your 60-second elevator pitch (memorize this)

Sikkim is India's first organic state, but "Sikkim organic" labels are easy to fake. We built a traceability app where a farmer registers a batch and gets a QR code. Every time the product changes hands, a handler records a cryptographically signed event, chained together by hashes so history can't be altered without detection. A customer scans the QR and instantly sees the full verified journey and whether it's intact. And periodically we publish a single fingerprint of all events to the Ethereum blockchain as an independent proof. No wallet needed for consumers, no expensive hardware.

---

## Part 9 — Questions they might ask (and quick answers)

- **"So it's not actually blockchain?"** — The events use the same idea — a tamper-evident hash chain — stored in a normal database, which is faster and cheaper. We anchor a Merkle root to real Ethereum for independent proof. This is the standard "off-chain data + on-chain reference" pattern, chosen to avoid Hyperledger's complexity.
- **"Why not every event on the blockchain?"** — Cost and speed. Writing thousands of transactions is expensive and slow. One Merkle root proves all of them at once.
- **"How does tampering get caught?"** — We recompute every hash from scratch and compare. If any data was edited, the recomputed chain breaks and we report exactly which event.
- **"Why Ed25519?"** — It's a fast, modern signature scheme. Each participant signs their events; the public key verifies the signature, so you can prove who did what.
- **"What did you cut and why?"** — Hyperledger Fabric (too complex for a semester), IoT/RFID sensors (not needed for signed events), and consumer wallets (kills adoption).

---

## Appendix — Concept Q&A (the deeper questions)

### What is uvicorn?

It's the **program that runs your Python web app** and serves it over the internet.

- FastAPI just *defines* your app (routes, logic). It doesn't actually *listen* for requests.
- **Uvicorn** is the server that takes that app, opens a port (8000), waits for HTTP requests, and hands each one to FastAPI.
- Analogy: FastAPI is the restaurant kitchen; uvicorn is the front door + waiters taking orders in and food out.

```
uvicorn app.main:app --reload --port 8000
```

"Run the `app` object inside `app/main.py`, on port 8000, and `--reload` = restart automatically when I change the code." (Running it on the wrong port is why the frontend got a 502 earlier.)

### What does `emit` do in Solidity?

`emit` **writes a log message** to the blockchain that anyone can look at later.

- `event Anchored(...)` declares a *type* of log message (an "event").
- `emit Anchored(...)` fires that log at the moment the function runs.

Why it matters: storing data in state (`mapping`/`count`) costs gas and stays forever, but **events** are a cheaper, permanent record that block explorers (like Etherscan) display — so you can prove "this Merkle root was anchored at this timestamp, in this transaction". `indexed` makes a field searchable.

Analogy: `mapping` is writing in a ledger book; `emit` is also shouting it out loud so everyone's copy of the transcript records it.

### What is Ed25519?

A **digital signature algorithm** — a way to prove a message came from a specific person without revealing their secret.

Two keys: a **private key** (secret, used to *sign*) and a **public key** (shared, used to *verify*).

```python
sig = sign_message(private_key, "this is my event")   # only the key owner can do this
verify_signature(public_key, "this is my event", sig) # anyone can check: True/False
```

Properties:

- You **can't fake** a signature without the private key.
- You **can't tamper** with the message after signing — change one character and verification fails.
- "25519" is just the name of the elliptic curve it's built on (Edwards-curve, 25519). Don't overthink the name.

Analogy: the private key is your unique pen + handwriting, the public key is a published sample of your handwriting, the signature is your actual signed name — anyone can compare the signature to your known handwriting to confirm it's really you.

In our project: each participant (farmer, trucker) gets a keypair and signs their events, so the system proves *who* recorded each step and that it wasn't altered.

### Merkle root — explained slowly

**The problem:** we have thousands of events and want ONE small number that "summarizes" all of them, such that changing any single event changes that number.

**How it's built (bottom-up):**

Step 1 — hash each event individually (its fingerprint):

```
event1 -> A    event2 -> B    event3 -> C    event4 -> D
```

Step 2 — pair them up and hash each pair:

```
hash(A + B) = AB
hash(C + D) = CD
```

Step 3 — repeat until only one is left:

```
hash(AB + CD) = ABCD   <- this is the Merkle root
```

The final single hash `ABCD` is the **Merkle root** — one 64-character string representing all 4 events.

**Key properties:**

- **Tiny:** one hash represents millions of events.
- **Sensitive:** change `event2` → `B` changes → `AB` changes → `ABCD` changes. The root always reflects the data.
- **Provable:** you can prove "event3 is in this tree" without showing the other events — just a few hashes along the path.

**The tree shape:**

```
          ABCD          <- root (we anchor this to Ethereum)
         /    \
       AB      CD
      /  \    /  \
     A    B  C    D    <- individual event hashes
```

**Odd count?** Duplicate the last one before pairing (the `layer.append(layer[-1])` line in the code):

```
A  B  C  ->  A  B  C  C  ->  AB  CC  ->  root
```

**Why we use it:** instead of paying to store 1000 events on Ethereum, we store just the root. Later, anyone recomputes the root from our events and compares it to the one on-chain. Match = untouched; mismatch = tampered.

---

*Generated as a companion to `docs/PROJECT.md` and `docs/FINAL_REPORT.md` for the project presentation.*
