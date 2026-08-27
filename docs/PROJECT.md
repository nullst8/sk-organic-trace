# Sikkim Organic Produce Provenance

**Project Based Learning — Supply Chain Traceability Using Blockchain in the Food Industry**

| Field | Value |
|---|---|
| Institution | Sikkim Manipal Institute of Technology (SMIT) |
| Department | Computer Science and Engineering |
| Supervisor | Dr. Sandeep Gurung |
| Team | Manas Prakash (202400731), Aayush Nandan (202400541), Riddhi Bhagat (202400703), Aryan Kumar Pitambar (202400301), Hardik Pratap Singh (202400745) |
| Stack | Python (FastAPI) backend · React (Vite) frontend · Solidity anchor contract · SQLite |
| Hardware / IoT | None (explicitly out of scope) |

---

## 1. Problem

Sikkim is India’s first fully organic state. Produce sold as “Sikkim organic” (cardamom, ginger, turmeric, mandarin, etc.) is frequently mislabelled. Traditional traceability relies on paper records and central databases that are easy to alter and hard for a consumer to check.

Your literature review (Walmart/IBM Food Trust, Tian, Casino, Marchese & Tomarchio, Kshetri, etc.) shows that blockchain can give end-to-end visibility, but also that **cost, skills, Hyperledger complexity, and small-producer exclusion** block real adoption. This project keeps the value of the idea (unique batch IDs, signed handoffs, tamper-evident history, QR for consumers) and drops the parts that do not fit a college semester or a rural supply chain.

---

## 2. What We Build

A **mobile-first web app** for organic produce provenance:

1. A farmer or co-op **registers a batch** and gets a unique ID + QR label.
2. Each handler (collection centre, processor, transporter, retailer) **records a signed handoff event**.
3. A consumer **scans the QR** and sees the verified journey plus a **chain intact / tampered** verdict.
4. Periodically, a **Merkle root** of new events is **anchored** to a public EVM testnet so anyone can check integrity against a public ledger.

No sensors, no RFID readers, no Hyperledger Fabric network, no MetaMask for consumers.

---

## 3. Scope Decisions (What We Cut and Why)

| Cut from synopsis | Why |
|---|---|
| Hyperledger Fabric + MSP | Semester would be spent on Docker/YAML; nothing user-facing to demo |
| IoT / RFID / ESP32 | Hardware flakiness; not required for provenance of signed events |
| Zero-knowledge proofs | Advanced crypto; not needed for the demo or the research story |
| MetaMask for consumers | Kills adoption; consumer page is read-only and wallet-free |
| Real mainnet payments | Cost and KYC; use a free testnet for anchoring only |

These cuts are intentional and should be stated in the final report under “Scope and limitations,” citing the adoption barriers already listed in your key findings (cost, skills, interoperability, off-chain storage).

---

## 4. Architecture

```
┌─────────────────┐     HTTP/JSON      ┌──────────────────────────┐
│  React PWA      │ ─────────────────► │  FastAPI (Python)        │
│  (Vite)         │ ◄───────────────── │  /api/...                │
│  Roles:         │                    │  SQLite (events chain)   │
│  - Producer     │                    │  Ed25519 verify          │
│  - Handler      │                    │  Merkle root builder     │
│  - Consumer     │                    │  Anchoring job           │
└─────────────────┘                    └────────────┬─────────────┘
                                                    │ publish root
                                                    ▼
                                       ┌──────────────────────────┐
                                       │  Solidity ProvenanceAnchor│
                                       │  (Polygon Amoy / Sepolia) │
                                       └──────────────────────────┘
```

### How Python backend connects to React frontend

They do **not** share a process or language. They talk over **HTTP**:

1. FastAPI listens on `http://localhost:8000` and returns JSON.
2. React (Vite) runs on `http://localhost:5173` and calls those URLs with `fetch`.
3. In development, Vite proxies `/api` → `http://localhost:8000` so the browser stays same-origin and you avoid CORS pain.
4. In production, Nginx (or similar) serves the built React files and reverse-proxies `/api` to uvicorn.

Example:

```ts
const res = await fetch("/api/batches/abc123");
const data = await res.json();
```

That is the entire integration surface.

---

## 5. Tech Stack

| Layer | Choice | Role |
|---|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Pydantic | REST API, validation, business logic |
| Database | SQLite (file) | Simple deploy for demos; schema is Postgres-ready |
| Crypto | `cryptography` (Ed25519), SHA-256 | Sign/verify events; hash chain |
| Frontend | React + TypeScript + Vite (**pnpm**) | Producer/handler UI + consumer scan page |
| QR | `qrcode` (server) / `html5-qrcode` (client) | Label generation and scanning |
| Chain anchor | Solidity contract on EVM testnet | Store Merkle roots publicly |
| Auth (demo) | Simple API keys / role tokens | Enough for PBL; not production IAM |

---

## 6. Data Model

### Participants

| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| name | string | Farm / co-op / company name |
| role | enum | `producer`, `handler`, `retailer`, `regulator` |
| public_key | string | Ed25519 public key (hex/base64) |
| created_at | datetime | |

### Batches

| Field | Type | Notes |
|---|---|---|
| id | UUID | Also used in QR payload |
| product_name | string | e.g. Large Cardamom |
| origin | string | Village / district |
| organic_claim | bool | Claimed organic |
| producer_id | FK | Who registered |
| created_at | datetime | |

### Events (append-only hash chain)

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| batch_id | FK | |
| event_type | enum | `harvest`, `handoff`, `process`, `ship`, `retail` |
| actor_id | FK | Participant who submitted |
| payload_json | text | Canonical JSON of the event body |
| prev_hash | string | Hash of previous event for this batch (or genesis) |
| hash | string | SHA256 of prev_hash + canonical_payload + signature |
| signature | string | Ed25519 over canonical payload |
| created_at | datetime | |

### Anchors

| Field | Type | Notes |
|---|---|---|
| id | int | |
| merkle_root | string | Hex |
| from_event_seq | int | Inclusive range covered |
| to_event_seq | int | |
| tx_hash | string | Testnet transaction hash |
| anchored_at | datetime | |

---

## 7. Cryptographic Design

### Hash chain (per batch)

1. Genesis: `prev_hash = "0" * 64`
2. For each new event: build **canonical JSON** (sorted keys, no whitespace variance).
3. Verify Ed25519 signature against the actor’s registered public key; reject if invalid.
4. `hash = SHA256(prev_hash + canonical_payload + signature)` (UTF-8 bytes).
5. Store row; never UPDATE event rows in application code.

### Verifier

A CLI/API walks events in order for a batch (or globally), recomputes hashes, and reports the first break. Demo for examiners: edit a row in SQLite by hand → verifier fails → recomputed Merkle root no longer matches the on-chain anchor.

### Merkle anchoring

1. Collect new event hashes since last anchor.
2. Build a binary Merkle tree; store root.
3. Call `ProvenanceAnchor.anchor(bytes32 root)` on the testnet.
4. Consumer / auditor page links to the block explorer.

### Signatures (demo workflow)

For the scaffold, the server can generate a keypair per participant and sign on the server when a trusted role submits an event (simpler for demos). The production-oriented design is **client-side WebCrypto signing** so the private key never leaves the device; the API only verifies. Document both; implement server-assisted signing first so the team can demo without wallet UX.

---

## 8. API Surface (v1)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/participants` | Register participant + public key |
| GET | `/api/participants` | List participants |
| POST | `/api/batches` | Create batch |
| GET | `/api/batches/{id}` | Batch summary + events |
| POST | `/api/batches/{id}/events` | Append signed event |
| GET | `/api/batches/{id}/verify` | Run hash-chain verify |
| GET | `/api/batches/{id}/qr` | PNG/SVG QR for the batch |
| POST | `/api/anchors` | Build Merkle root and (optionally) submit tx |
| GET | `/api/anchors` | List anchors |
| GET | `/api/health` | Liveness |

CORS: allow `http://localhost:5173` in development.

---

## 9. Frontend Screens

1. **Home** — short brand pitch + “Scan product” / “Sign in as producer.”
2. **Producer** — create batch (product, origin), show QR to print/share.
3. **Handler** — select batch, add handoff/process/ship event.
4. **Consumer** — scan QR (or paste batch ID); timeline of events; **Chain intact / Tampered**; link to latest anchor tx if present.
5. **Admin / Verify** — run verify on a batch; show Merkle / explorer link.

Offline-first (later phase): queue handler events in IndexedDB when offline; sync when connectivity returns. Scaffold may start online-only.

---

## 10. Approach by Phase

### Phase 0 — Foundations (done in this repo scaffold)

- Repo layout, `PROJECT.md` / `PROJECT.docx`, FastAPI health + models, React Vite app with proxy, Solidity stub, How to Run.

### Phase 1 — Ledger core

- Participants, batches, events tables.
- Canonical JSON + hash chain + verify endpoint/CLI.
- Unit tests: append, verify OK, tamper detection.

### Phase 2 — API + producer/handler UI

- CRUD/batch create, event append with signature check.
- React forms for producer and handler roles.

### Phase 3 — Consumer + QR

- QR generation and scan page.
- Timeline + verify badge.

### Phase 4 — Anchoring

- Merkle builder + Solidity deploy to testnet.
- Store `tx_hash`; show on consumer page.

### Phase 5 — Polish + evaluation

- Offline sync (optional).
- Benchmarks: verify latency, event write throughput, anchor gas (testnet).
- Field story: one local vendor / co-op walkthrough for the report.
- Final report: scope cuts, metrics, demo script (tamper → verify fails).

---

## 11. Team Module Split (5 members)

| Member | Module |
|---|---|
| 1 | Ledger core: hash chain, verifier CLI/API, tests |
| 2 | FastAPI: models, routes, DB, CORS, auth tokens |
| 3 | React: producer + handler flows, API client |
| 4 | React: consumer scan, QR, timeline, verify badge |
| 5 | Anchoring: Solidity, Merkle, scripts, benchmarks + docs |

Integrate weekly; do not wait until the end to merge.

---

## 12. Evaluation / Demo Script

1. Create producer + batch; print/show QR.
2. Add two handoff events.
3. Consumer scan → **Chain intact**.
4. Open SQLite, alter one `payload_json` or `hash`.
5. Call `/verify` → **Tampered** at the broken link.
6. (After Phase 4) Show Merkle root on explorer ≠ recomputed root after tamper.

Collect numbers for the report: time to trace retail → farm, verify duration, events/sec under load script.

---

## 13. Repository Layout

```
pbl/
├── docs/
│   ├── PROJECT.md          # This document
│   ├── PROJECT.docx        # Same content for submission
│   └── generate_docx.py    # Regenerates the .docx from .md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── crypto_chain.py
│   │   ├── chain.py
│   │   ├── settings.py
│   │   └── routers.py
│   ├── tests/              # pytest suite (crypto + API + tamper)
│   ├── scripts/            # demo_flow.py, benchmark.py
│   ├── deploy_anchor.py
│   └── requirements.txt
├── frontend/
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── vite.config.ts
│   └── src/...
├── contracts/
│   └── ProvenanceAnchor.sol
├── pbl_report.pdf          # Original synopsis
└── README.md               # Points to docs + How to Run
```

Package manager for the frontend is **pnpm** (not npm). Use `pnpm install` / `pnpm dev` / `pnpm build`.

---

## 14. How to Run

### Prerequisites

- Python 3.11 or newer
- Node.js 20+ and **pnpm** (`npm install -g pnpm` if needed)
- (Optional, Phase 4) MetaMask + testnet ETH/MATIC faucet for deploying the contract

### One-time setup

```bash
cd /path/to/pbl

# Backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# Frontend (pnpm)
cd frontend
pnpm install
cd ..
```

### Run backend (terminal 1)

```bash
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000  
- Interactive docs: http://localhost:8000/docs  
- Health: http://localhost:8000/api/health  

### Run frontend (terminal 2)

```bash
cd frontend
pnpm dev
```

- App: http://localhost:5173  
- `/api` is proxied to port 8000 (see `vite.config.ts`).

### Quick smoke test

```bash
curl -s http://localhost:8000/api/health
# expect: {"status":"ok","service":"sikkim-provenance"}
```

### Run tests

```bash
source .venv/bin/activate
cd backend
python -m pytest tests/ -q
```

Open http://127.0.0.1:5173 — you should see the home page and be able to hit the health check from the UI.

### Blockchain anchoring

By default (no `.env`), `POST /api/anchors` deploys/`anchor()`s on an **in-process Ethereum tester** and stores a real `tx_hash` with `dry_run: false`.

For a public testnet (Sepolia / Polygon Amoy):

1. Copy `backend/.env.example` → `backend/.env`
2. Fund a wallet from a faucet; set `ANCHOR_RPC_URL` and `ANCHOR_PRIVATE_KEY`
3. Deploy: `cd backend && source ../.venv/bin/activate && python deploy_anchor.py`
4. Set `ANCHOR_CONTRACT_ADDRESS` to the printed address
5. Restart uvicorn; `POST /api/anchors` submits to that network

Check mode: `GET /api/chain/status`

### Regenerate PROJECT.docx

```bash
source .venv/bin/activate
pip install python-docx   # if not already installed
python docs/generate_docx.py
```

### Database file

SQLite file is created at `backend/provenance.db` on first API start. Delete it to reset demo data.

### Phase 4 (later): deploy anchor contract

1. Install Foundry or Hardhat (team choice; document in contract README when added).
2. Deploy `contracts/ProvenanceAnchor.sol` to Polygon Amoy or Sepolia.
3. Put `ANCHOR_RPC_URL`, `ANCHOR_PRIVATE_KEY`, `ANCHOR_CONTRACT_ADDRESS` in `backend/.env`.
4. `POST /api/anchors` builds the Merkle root and submits (or records a dry-run root if keys are missing).

---

## 15. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Team splits and never integrates | Weekly merge + shared OpenAPI from `/docs` |
| Scope creep back to Fabric/IoT | Keep this doc as the contract with the supervisor |
| Signature UX too hard | Server-assisted signing in Phase 1–3; client signing later |
| Testnet faucets change | Document dry-run anchoring without a live tx |

---

## 16. Alignment With PBL Synopsis

| Synopsis goal | How this project meets it |
|---|---|
| End-to-end farm → consumer | Batch + staged events + consumer QR |
| Immutable records | Hash chain + optional public Merkle anchor |
| Permissioned participants | Registered participants + public keys |
| Smart contracts | On-chain `anchor()`; rules for event types in API |
| Off-chain storage + on-chain reference | Events in SQLite; roots on-chain |
| Real-world use | Sikkim organic labelling / consumer trust |

---

*Document version: 1.0 — living doc; update this file whenever architecture or run steps change, then regenerate the `.docx`.*
