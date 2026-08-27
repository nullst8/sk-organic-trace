# Presentation Slides — Sikkim Organic Trace

Use as speaker notes / convert to PPT. One slide per `##`.

---

## 1. Title

**Sikkim Organic Trace**  
Supply Chain Traceability Using Blockchain in the Food Industry  
SMIT CSE · PBL · Dr. Sandeep Gurung  
Team: Manas, Aayush, Riddhi, Aryan, Hardik

---

## 2. The problem

- Sikkim = India’s first organic state  
- Mislabelling of “Sikkim organic” erodes trust  
- Paper / central DBs are slow to audit and easy to alter  

---

## 3. What literature says

- Blockchain helps (Walmart/IBM, Tian, …)  
- Gaps: cost, skills, Fabric complexity, small-farm exclusion  
- **Our bet:** keep integrity + QR; drop overbuilt stack  

---

## 4. What we built

1. Producer registers batch → QR  
2. Handlers sign handoffs on a hash chain  
3. Consumer scans → timeline + **intact / tampered**  
4. Merkle root anchored on Ethereum  

---

## 5. Architecture (one diagram)

React PWA → FastAPI/SQLite (events + Ed25519) → Merkle root → `ProvenanceAnchor` on Sepolia  

No wallet for consumers. No IoT.

---

## 6. Scope cuts (and why)

| Dropped | Reason |
|---|---|
| Hyperledger Fabric | Too heavy for semester |
| IoT / RFID | Not needed for signed events |
| ZKP / MetaMask UX | Adoption + complexity |

---

## 7. Live demo

1. Create batch + QR  
2. Add handoffs  
3. Scan / verify → intact  
4. Tamper SQLite row → broken  
5. Show on-chain tx / explorer  

---

## 8. Numbers

- Verify latency: see `docs/benchmarks.json`  
- Trace time: milliseconds vs days of paper recall  
- Concurrent writes: fixed with unique `seq` + lock  

---

## 9. Blockchain honesty

- Events live **off-chain**  
- Chain stores a **fingerprint** (Merkle root)  
- Feasible, cheap on Sepolia — not every event on mainnet  

---

## 10. Closing

Usable provenance for Sikkim organic produce:  
**simple enough to finish, real enough to matter.**  
Questions?
