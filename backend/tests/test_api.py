from app.crypto_chain import GENESIS_HASH


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok", "service": "sikkim-provenance"}


def test_create_participant_and_list(client, producer, handler):
    assert producer["role"] == "producer"
    assert len(producer["public_key"]) == 64
    assert "private_key_demo" not in producer

    resp = client.get("/api/participants")
    assert resp.status_code == 200
    roles = {p["role"] for p in resp.json()}
    assert roles == {"producer", "handler"}


def test_create_participant_invalid_role_422(client):
    resp = client.post("/api/participants", json={"name": "X", "role": "auditor"})
    assert resp.status_code == 422


def test_batch_creates_genesis_harvest(client, batch):
    assert batch["organic_claim"] is True
    events = batch["events"]
    assert len(events) == 1
    ev = events[0]
    assert ev["event_type"] == "harvest"
    assert ev["prev_hash"] == GENESIS_HASH
    assert len(ev["hash"]) == 64
    assert len(ev["signature"]) == 128


def test_batch_requires_producer_role(client, handler):
    resp = client.post(
        "/api/batches",
        json={
            "product_name": "X",
            "origin": "Y",
            "organic_claim": True,
            "producer_id": handler["id"],
        },
    )
    assert resp.status_code == 400


def test_batch_unknown_producer_404(client):
    resp = client.post(
        "/api/batches",
        json={
            "product_name": "X",
            "origin": "Y",
            "organic_claim": True,
            "producer_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert resp.status_code == 404


def test_append_events_chain(client, batch, handler):
    prev = batch["events"][0]["hash"]
    for et in ["handoff", "process", "ship", "retail"]:
        resp = client.post(
            f"/api/batches/{batch['id']}/events",
            json={"event_type": et, "actor_id": handler["id"], "details": {"note": et}},
        )
        assert resp.status_code == 200
        ev = resp.json()
        assert ev["prev_hash"] == prev
        prev = ev["hash"]


def test_append_harvest_rejected(client, batch, producer):
    resp = client.post(
        f"/api/batches/{batch['id']}/events",
        json={"event_type": "harvest", "actor_id": producer["id"]},
    )
    assert resp.status_code == 400


def test_append_unknown_batch_or_actor_404(client, batch, handler):
    resp = client.post(
        f"/api/batches/{batch['id']}/events",
        json={"event_type": "handoff", "actor_id": "missing"},
    )
    assert resp.status_code == 404

    resp = client.post(
        "/api/batches/nope/events",
        json={"event_type": "handoff", "actor_id": handler["id"]},
    )
    assert resp.status_code == 404


def test_invalid_signature_rejected(client, batch, handler):
    resp = client.post(
        f"/api/batches/{batch['id']}/events",
        json={
            "event_type": "handoff",
            "actor_id": handler["id"],
            "details": {},
            "signature": "00" * 64,
        },
    )
    assert resp.status_code == 400


def test_verify_intact(client, batch, handler):
    for et in ["handoff", "process"]:
        client.post(
            f"/api/batches/{batch['id']}/events",
            json={"event_type": et, "actor_id": handler["id"], "details": {}},
        )
    resp = client.get(f"/api/batches/{batch['id']}/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body["intact"] is True
    assert body["event_count"] == 3
    assert body["broken_at_seq"] is None


def test_verify_detects_tamper(app_env, client, batch, handler):
    for et in ["handoff", "process"]:
        client.post(
            f"/api/batches/{batch['id']}/events",
            json={"event_type": et, "actor_id": handler["id"], "details": {}},
        )

    intact = client.get(f"/api/batches/{batch['id']}/verify").json()
    assert intact["intact"] is True

    from app.models import Event

    db = app_env.Session()
    first = db.query(Event).filter(Event.batch_id == batch["id"]).order_by(Event.seq).first()
    first_seq = first.seq
    first.payload_json = first.payload_json + "TAMPER"
    db.commit()
    db.close()

    broken = client.get(f"/api/batches/{batch['id']}/verify").json()
    assert broken["intact"] is False
    assert broken["broken_at_seq"] == first_seq
    assert "seq" in broken["message"]


def test_qr_returns_png(client, batch):
    resp = client.get(f"/api/batches/{batch['id']}/qr")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_qr_unknown_batch_404(client):
    assert client.get("/api/batches/nope/qr").status_code == 404


def test_get_and_list_batches(client, batch):
    got = client.get(f"/api/batches/{batch['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == batch["id"]

    listed = client.get("/api/batches").json()
    assert any(b["id"] == batch["id"] for b in listed)

    assert client.get("/api/batches/nope").status_code == 404
