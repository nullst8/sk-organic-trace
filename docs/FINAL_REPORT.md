# Final Project Report

**Sikkim Organic Produce Provenance**  
Project Based Learning — Supply Chain Traceability Using Blockchain in the Food Industry

| Field | Value |
|---|---|
| Institution | Sikkim Manipal Institute of Technology (SMIT) |
| Department | Computer Science and Engineering |
| Supervisor | Dr. Sandeep Gurung |
| Team | Manas Prakash, Aayush Nandan, Riddhi Bhagat, Aryan Kumar Pitambar, Hardik Pratap Singh |

---

## 1. Abstract

We built a mobile-first provenance system for Sikkim organic produce. Farmers register batches, handlers append cryptographically signed handoff events to a hash chain, and consumers verify product history by scanning a QR code. Merkle roots of event hashes are anchored on Ethereum (Sepolia when funded; local Ethereum tester otherwise), matching the “off-chain data + on-chain integrity reference” pattern from the literature without requiring Hyperledger Fabric or IoT hardware.

## 2. Problem and motivation

Sikkim is India’s first fully organic state, yet mislabelling of “Sikkim organic” goods remains a trust problem. Traditional paper and centralised databases are easy to alter. Our literature review (Walmart/IBM Food Trust, Tian, Casino, Marchese & Tomarchio, Kshetri, Vu et al.) shows blockchain can improve traceability, but also that **cost, skills, Fabric complexity, and exclusion of small producers** block adoption. This project keeps the valuable core—unique batch IDs, signed events, tamper evidence, consumer QR—and cuts the parts that do not fit a college semester or a rural supply chain.

## 3. Scope decisions

| Cut | Why |
|---|---|
| Hyperledger Fabric + MSP | Semester would be spent on infrastructure, not a usable demo |
| IoT / RFID | Not required for signed event provenance |
| Zero-knowledge proofs | Unnecessary for the evaluation story |
| MetaMask for consumers | Kills adoption; consumer page is wallet-free |
| Every event as a mainnet tx | Cost and latency; we anchor Merkle roots instead |

## 4. Architecture

```
React (Vite/pnpm)  --HTTP/JSON-->  FastAPI + SQLite
                                      | hash chain + Ed25519
                                      | Merkle root
                                      v
                               ProvenanceAnchor.sol
                               (Sepolia or local tester)
```

- **Off-chain:** event payloads, signatures, QR labels  
- **On-chain:** 32-byte Merkle root via `anchor(bytes32)`  
- **Frontend ↔ backend:** Vite proxies `/api` to port 8000  

## 5. Implementation highlights

1. **Hash chain** — each event stores `prev_hash` and `SHA256(prev_hash || payload || signature)`.  
2. **Ed25519** — per-participant keys; server-assisted signing for demos.  
3. **Concurrency fix** — `UNIQUE(seq)` + process lock + savepoint retries.  
4. **QR** — server PNG generation; consumer camera scan via `html5-qrcode`.  
5. **Ethereum** — `web3.py` + Solidity contract; Sepolia via `backend/.env` and `deploy_anchor.py`.  

## 6. Evaluation / demo script

1. Register producer and create a cardamom batch → show QR.  
2. Append handoff / process / ship / retail.  
3. Consumer scan or `/trace/{id}` → **Chain intact**.  
4. Edit one SQLite event → **Tampered** at `broken_at_seq`.  
5. `POST /api/anchors` → show `tx_hash` (and Sepolia explorer link when configured).  

Automated: `python backend/scripts/demo_flow.py` and `python backend/scripts/benchmark.py` (writes `docs/benchmarks.json`).

## 7. Benchmarks

Measured on the local FastAPI instance (anchor mode: `local-eth-tester`). Raw data: `docs/benchmarks.json` (last run synced into this report).

| Metric | Value |
|---|---|
| Events in sample batch | 5 |
| Create batch | 34.25 ms |
| Event write (mean) | 38.45 ms |
| Event write (p95) | 44.83 ms |
| Verify (mean of 20) | 4.8 ms |
| Verify (p95) | 10.78 ms |
| Get batch | 1.74 ms |
| Anchor Merkle root | 108.44 ms |
| Manual / paper recall (literature) | days |
| Digital farm→retail verify | ~4.8 ms |

Tamper detection is demonstrated by `python backend/scripts/demo_flow.py` (intact → corrupt SQLite → `broken_at_seq`).


## 8. Blockchain honesty

| Layer | What it is |
|---|---|
| SQLite hash chain | Tamper-evident local ledger |
| Merkle root | Compresses many events into one digest |
| Ethereum anchor | Public commitment so history cannot be silently rewritten |
| Not claimed | Full Hyperledger consortium, IoT sensors, or mainnet per-event logging |

Until `ANCHOR_CONTRACT_ADDRESS` is set and the wallet is funded on Sepolia, anchors use an in-process Ethereum tester (still real EVM transactions, not a public explorer).

## 9. How to run (summary)

```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# other terminal
cd frontend && pnpm install && pnpm dev
```

Sepolia: fund the address from `GET /api/chain/status` → `python backend/deploy_anchor.py` → restart API.

## 10. Conclusion

The system demonstrates end-to-end farm-to-consumer provenance suitable for a PBL evaluation: usable UI, cryptographic integrity, and optional public Ethereum anchoring—without over-scoping into Fabric or hardware.
