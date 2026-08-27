#!/usr/bin/env python3

from __future__ import annotations

import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
DB = Path(__file__).resolve().parents[1] / "provenance.db"


def req(method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if body is not None else {}
    request = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as resp:
        return json.loads(resp.read().decode() or "null")


def main() -> None:
    print("=== Sikkim Organic Trace — live demo script ===\n")
    producer = req("POST", "/api/participants", {"name": "Dzongu Organic Co-op", "role": "producer"})
    handler = req("POST", "/api/participants", {"name": "Gangtok Packhouse", "role": "handler"})
    print("1. Registered producer + handler")

    batch = req(
        "POST",
        "/api/batches",
        {
            "product_name": "Large Cardamom",
            "origin": "Dzongu, North Sikkim",
            "organic_claim": True,
            "producer_id": producer["id"],
            "harvest_note": "Harvested after monsoon",
        },
    )
    bid = batch["id"]
    print(f"2. Created batch {bid}")
    print(f"   QR: {BASE}/api/batches/{bid}/qr")
    print(f"   Trace UI: http://127.0.0.1:5173/trace/{bid}")

    for et, note in [
        ("handoff", "Collected at co-op"),
        ("process", "Dried and graded"),
        ("ship", "Truck to Gangtok"),
        ("retail", "Shelf at MG Marg"),
    ]:
        req(
            "POST",
            f"/api/batches/{bid}/events",
            {"event_type": et, "actor_id": handler["id"], "details": {"note": note}},
        )
    print("3. Appended handoff → process → ship → retail")

    t0 = time.perf_counter()
    verify = req("GET", f"/api/batches/{bid}/verify")
    ms = (time.perf_counter() - t0) * 1000
    print(f"4. Verify: intact={verify['intact']} in {ms:.2f} ms — {verify['message']}")

    chain = req("GET", "/api/chain/status")
    print(f"5. Chain mode: {chain.get('mode')}")
    if chain.get("funding_address") and chain.get("mode") != "sepolia":
        print(f"   Fund {chain['funding_address']} then: python deploy_anchor.py")

    try:
        anchor = req("POST", "/api/anchors")
        print(
            f"6. Anchored Merkle root; dry_run={anchor['dry_run']} tx={anchor.get('tx_hash')}"
        )
        if anchor.get("explorer_url"):
            print(f"   Explorer: {anchor['explorer_url']}")
    except Exception as exc:
        print(f"6. Anchor skipped/failed: {exc}")

    print("\n7. Tamper demo — corrupting one event in SQLite…")
    con = sqlite3.connect(DB)
    row = con.execute(
        "SELECT id FROM events WHERE batch_id = ? ORDER BY seq LIMIT 1", (bid,)
    ).fetchone()
    if not row:
        print("No event to tamper", file=sys.stderr)
        sys.exit(1)
    con.execute("UPDATE events SET payload_json = payload_json || 'TAMPER' WHERE id = ?", (row[0],))
    con.commit()
    con.close()
    broken = req("GET", f"/api/batches/{bid}/verify")
    print(
        f"   After tamper: intact={broken['intact']} broken_at_seq={broken.get('broken_at_seq')} — {broken['message']}"
    )
    print("\nDemo complete. Examiner talking points: QR → timeline → intact → DB edit → broken.")


if __name__ == "__main__":
    main()
