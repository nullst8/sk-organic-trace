# Deploying Sikkim Organic Trace (free)

Host the **frontend + backend + smart contract** for $0.

| Piece | Where | Notes |
|---|---|---|
| Frontend (Vite build) | Served by the same FastAPI server | One URL, no CORS/proxy config |
| Backend (FastAPI) | **Render** free web service (Docker) | 512 MB, sleeps after 15 min idle |
| Database | **Neon** Postgres (free) | Persistent across sleeps/redeploys |
| Smart contract | Deployed to **Sepolia** testnet (free) | Optional — falls back to in-process eth-tester |

## Prerequisites

- GitHub repo (already done: `nullst8/sk-organic-trace`)
- Render account — https://render.com (free, no credit card)
- Neon account — https://neon.tech (free, no credit card)
- (optional) cron-job.org for an uptime pinger

---

## Step 0 — commit & push

```bash
git add Dockerfile .dockerignore render.yaml backend/app/database.py backend/app/models.py backend/app/routers.py backend/app/main.py backend/scripts/demo_flow.py backend/scripts/benchmark.py DEPLOY.md
git commit -m "chore: add Docker/render/Neon deployment + Postgres support"
git push origin main
```

*(You can also add the report/docs files — `PBL_report_final.docx`, `PROJECT_REPORT.pdf`, `docs/…` — in a separate commit if you want them in the repo. Leave `backup_PBL_final_latest-semi(12)new.pptx` untracked.)*

---

## Step 1 — Neon Postgres (2 minutes)

1. Sign up at https://neon.tech → **Create project** (any name/region).
2. On the project dashboard, copy the **connection string** (the pooled one is fine). It looks like:
   ```
   postgresql://user:password@ep-xxxx-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```
3. Keep it — this is your `DATABASE_URL` secret.

---

## Step 2 — Render web service (2 minutes)

**Option A — Blueprint (recommended).** The repo has `render.yaml`.

1. Render dashboard → **New** → **Blueprint** → connect `nullst8/sk-organic-trace`.
2. Render reads `render.yaml`; for the `DATABASE_URL` field paste the Neon connection string.
3. **Apply** → it deploys.

**Option B — Manual.**

1. **New** → **Web Service** → connect the repo.
2. Runtime: **Docker** (auto-detected from the `Dockerfile`).
3. Environment variable: `DATABASE_URL` = your Neon string (set as **secret**).
4. Leave `ANCHOR_FORCE_LOCAL` = `true` (or add it).
5. **Deploy**.

What happens on build (multi-stage `Dockerfile`): stage 1 runs `pnpm build` for the React app, stage 2 installs `backend/requirements.txt` and copies `frontend/dist` in. Start command is `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check `/api/health`.

---

## Step 3 — verify

```
https://<your-app>.onrender.com/api/health   → {"status":"ok","service":"sikkim-provenance"}
https://<your-app>.onrender.com/docs         → Swagger UI
https://<your-app>.onrender.com/             → the React app
https://<your-app>.onrender.com/trace/<id>   → consumer deep link (from a QR)
```

---

## Step 4 — keep it awake (recommended before the demo)

Render free instances **sleep after 15 min of no traffic** (first request then takes ~1 min). Add a free pinger:

1. https://console.cron-job.org → **Create cronjob**.
2. URL: `https://<your-app>.onrender.com/api/health`, schedule **every 10 minutes**.
3. This keeps it awake (720 hrs/mo fits in Render's 750 free hours).

---

## Step 5 — seed demo data (optional)

Create everything in the UI, or from your laptop:

```bash
source .venv/bin/activate
PROVENANCE_BASE=https://<your-app>.onrender.com python backend/scripts/demo_flow.py
```

(Data now lives in Neon, so it survives sleeps/restarts — you can seed it the night before.)

---

## Step 6 — Ethereum anchoring

- **Default (works now):** `ANCHOR_FORCE_LOCAL=true` → anchors run on an in-process Ethereum tester. Real EVM transactions, `dry_run: false`, no public explorer. Good enough for the demo.
- **Sepolia (more impressive, optional):** later, fund a fresh burner wallet from a Sepolia faucet, then run `python backend/deploy_anchor.py`, paste the printed address into Render as `ANCHOR_CONTRACT_ADDRESS`, set `ANCHOR_FORCE_LOCAL=false`, and optionally verify the source on sepolia.etherscan.io.

---

## 10-minute pre-demo checklist

- [ ] Open `https://<your-app>.onrender.com` once (wakes the service).
- [ ] Confirm the chain banner shows **local-eth-tester**.
- [ ] Producer → register → create batch → show QR.
- [ ] Handler → append `handoff` → `process` → `ship` → `retail`.
- [ ] Scan / trace the QR → **Chain intact** timeline.
- [ ] Admin → **Anchor latest events** → show the tx hash.
- [ ] (Tamper demo) run `demo_flow.py` or edit the DB → verify shows **Tampered**.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Loading page / 502 on first hit | Service was asleep; wait ~1 min, or add the pinger. |
| Build fails | Check Render build logs; make sure `frontend/pnpm-lock.yaml` is committed. |
| Events not persisting | Confirm `DATABASE_URL` is set (Neon), not the local SQLite path. |
| Anchor tx fails | Fine — it falls back to eth-tester; check `/api/chain/status`. |

## Security

- `DATABASE_URL` and any `ANCHOR_*` values are **Render secrets** — never committed to git.
- `backend/.env` is already in `.gitignore`.
- The private key currently in `backend/.env` has been sitting in plaintext — generate a **fresh burner wallet** before doing any Sepolia step.
