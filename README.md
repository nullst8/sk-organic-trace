# Sikkim Organic Trace (PBL)

Hash-chained provenance for Sikkim organic produce.

- **Docs:** [docs/PROJECT.md](docs/PROJECT.md) (also `docs/PROJECT.docx`)
- **Backend:** Python FastAPI (`backend/`)
- **Frontend:** React + Vite via **pnpm** (`frontend/`)
- **Contract:** `contracts/ProvenanceAnchor.sol` (Phase 4)

## Quick start

```bash
# Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend (other terminal) — requires pnpm
cd frontend
pnpm install
pnpm dev
```

Open http://127.0.0.1:5173 — API docs at http://127.0.0.1:8000/docs

**Docs:** `docs/FINAL_REPORT.md` / `.docx`, `docs/SLIDES.md`, `docs/benchmarks.json`  
**Demo:** `python backend/scripts/demo_flow.py`  
**Bench:** `python backend/scripts/benchmark.py`  

**Sepolia:** fund the address in `backend/sepolia_funding_address.txt`, then `cd backend && python deploy_anchor.py` and restart the API.

## Notes on behaviour

- **QR codes** encode an absolute URL (`<origin>/trace/<batch-id>`) so a phone camera can open them. The origin comes from the request; set `PUBLIC_BASE_URL` in `backend/.env` when the app sits behind a proxy or the Vite dev server.
- **Who may record what:** handlers cover handoff, process, ship and retail; retailers record retail; producers may record a handoff; regulators are read-only. The harvest event is created with the batch.
- **Anchor checks:** `GET /api/batches/{id}/verify?check_anchor=true` reports whether the anchor covering a batch still matches the stored events, and `GET /api/anchors/{id}/verify` recomputes the Merkle root and compares it with the root logged on-chain (when the chain can be read). Without a configured RPC, anchors live in an in-process Ethereum tester and are lost when the server restarts.
- **Contract bytecode** is embedded in `app/chain.py`, so no Solidity compiler download is needed at runtime. `python -c "from app.chain import compile_with_solc; print(compile_with_solc())"` regenerates it after a contract change.
- **Postgres:** `DATABASE_URL` values starting with `postgres://` or `postgresql://` are routed to the psycopg driver automatically.
