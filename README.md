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
