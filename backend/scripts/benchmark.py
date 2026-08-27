#!/usr/bin/env python3

from __future__ import annotations

import json
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parents[2] / "docs" / "benchmarks.json"


def req(method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if body is not None else {}
    request = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            raw = resp.read()
            ms = (time.perf_counter() - t0) * 1000
            return resp.status, json.loads(raw.decode() or "null"), ms
    except urllib.error.HTTPError as e:
        ms = (time.perf_counter() - t0) * 1000
        return e.code, json.loads(e.read().decode() or "{}"), ms


def main() -> None:
    st, health, _ = req("GET", "/api/health")
    if st != 200:
        raise SystemExit(f"Backend not healthy: {health}")

    _, producer, _ = req("POST", "/api/participants", {"name": "Bench Farm", "role": "producer"})
    _, handler, _ = req("POST", "/api/participants", {"name": "Bench Handler", "role": "handler"})

    write_samples: list[float] = []
    _, batch, create_ms = req(
        "POST",
        "/api/batches",
        {
            "product_name": "Large Cardamom",
            "origin": "Dzongu, North Sikkim",
            "organic_claim": True,
            "producer_id": producer["id"],
        },
    )
    write_samples.append(create_ms)
    batch_id = batch["id"]

    for i, et in enumerate(["handoff", "process", "ship", "retail"]):
        _, _, ms = req(
            "POST",
            f"/api/batches/{batch_id}/events",
            {"event_type": et, "actor_id": handler["id"], "details": {"step": i}},
        )
        write_samples.append(ms)

    verify_samples: list[float] = []
    for _ in range(20):
        _, verify, ms = req("GET", f"/api/batches/{batch_id}/verify")
        assert verify["intact"] is True
        verify_samples.append(ms)

    _, _, get_ms = req("GET", f"/api/batches/{batch_id}")
    _, chain, _ = req("GET", "/api/chain/status")
    _, anchor, anchor_ms = req("POST", "/api/anchors")

    paper_baseline_seconds = 2 * 24 * 3600
    result = {
        "batch_id": batch_id,
        "event_count": 5,
        "create_batch_ms": round(create_ms, 2),
        "event_write_ms_mean": round(statistics.mean(write_samples), 2),
        "event_write_ms_p95": round(sorted(write_samples)[int(0.95 * (len(write_samples) - 1))], 2),
        "verify_ms_mean": round(statistics.mean(verify_samples), 2),
        "verify_ms_p95": round(sorted(verify_samples)[int(0.95 * (len(verify_samples) - 1))], 2),
        "get_batch_ms": round(get_ms, 2),
        "anchor_ms": round(anchor_ms, 2),
        "anchor": {
            "dry_run": anchor.get("dry_run"),
            "tx_hash": anchor.get("tx_hash"),
            "explorer_url": anchor.get("explorer_url"),
            "merkle_root": anchor.get("merkle_root"),
        },
        "chain_mode": chain.get("mode"),
        "paper_trace_baseline": "days (manual / paper recall, per Walmart/IBM literature)",
        "digital_trace_ms_mean": round(statistics.mean(verify_samples), 2),
    }
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
