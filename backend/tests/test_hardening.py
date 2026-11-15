import pytest
from sqlalchemy import select, text

from app import models
from app.crypto_chain import canonical_json, event_hash, sign_message


def _event(client, batch_id, actor, kind="handoff"):
    return client.post(
        f"/api/batches/{batch_id}/events",
        json={"event_type": kind, "actor_id": actor["id"], "details": {}},
    )


def _participant(client, role):
    return client.post("/api/participants", json={"name": role, "role": role}).json()


def test_regulator_cannot_record_events(client, batch):
    reg = _participant(client, "regulator")
    resp = _event(client, batch["id"], reg)
    assert resp.status_code == 403


def test_retailer_only_records_retail(client, batch):
    shop = _participant(client, "retailer")
    assert _event(client, batch["id"], shop, "ship").status_code == 403
    assert _event(client, batch["id"], shop, "retail").status_code == 200


def test_producer_cannot_log_retail(client, batch, producer):
    assert _event(client, batch["id"], producer, "retail").status_code == 403
    assert _event(client, batch["id"], producer, "handoff").status_code == 200


def test_handler_covers_the_middle_of_the_chain(client, batch, handler):
    for kind in ("handoff", "process", "ship", "retail"):
        assert _event(client, batch["id"], handler, kind).status_code == 200


def test_trace_url_is_absolute(client, batch):
    url = client.get(f"/api/batches/{batch['id']}/trace-url").json()["url"]
    assert url.startswith("http://") and url.endswith(f"/trace/{batch['id']}")
    assert client.get("/api/batches/nope/trace-url").status_code == 404


def test_trace_url_honours_public_base_url(client, batch, monkeypatch):
    from app.settings import settings

    monkeypatch.setattr(settings, "public_base_url", "https://trace.example.org/")
    url = client.get(f"/api/batches/{batch['id']}/trace-url").json()["url"]
    assert url == f"https://trace.example.org/trace/{batch['id']}"


def test_verify_reports_anchor_status(client, batch, handler):
    _event(client, batch["id"], handler)
    plain = client.get(f"/api/batches/{batch['id']}/verify").json()
    assert plain["anchor_status"] is None
    before = client.get(f"/api/batches/{batch['id']}/verify?check_anchor=true").json()
    assert before["intact"] and before["anchor_status"] == "not_anchored"
    assert client.post("/api/anchors").status_code == 200
    after = client.get(f"/api/batches/{batch['id']}/verify?check_anchor=true").json()
    assert after["intact"] and after["anchor_status"] == "ok" and after["anchor_id"] == 1


def test_anchor_verify_matches_untouched_events(client, batch, handler):
    _event(client, batch["id"], handler)
    anchor = client.post("/api/anchors").json()
    check = client.get(f"/api/anchors/{anchor['id']}/verify").json()
    assert check["events_match"] and check["events_found"] == check["events_expected"] == 2
    assert check["on_chain_match"] in (True, None)
    assert client.get("/api/anchors/999/verify").status_code == 404


def test_rewritten_tail_with_valid_signature_is_caught_by_anchor(app_env, client, batch, handler):
    """An attacker holding the actor's key can re-sign and re-hash, so the chain walk
    passes. The anchored root still changes."""
    _event(client, batch["id"], handler, "process")
    anchor = client.post("/api/anchors").json()

    with app_env.Session() as db:
        events = db.scalars(
            select(models.Event).where(models.Event.batch_id == batch["id"]).order_by(models.Event.seq)
        ).all()
        victim = events[-1]
        actor = db.get(models.Participant, victim.actor_id)
        payload = canonical_json({"forged": True})
        victim.payload_json = payload
        victim.signature = sign_message(actor.private_key_demo, payload)
        victim.hash = event_hash(victim.prev_hash, payload, victim.signature)
        db.commit()

    chain = client.get(f"/api/batches/{batch['id']}/verify?check_anchor=true").json()
    assert chain["intact"] is True
    assert chain["anchor_status"] == "mismatch"
    check = client.get(f"/api/anchors/{anchor['id']}/verify").json()
    assert check["events_match"] is False
    assert check["recomputed_root"] != check["stored_root"]


def test_deleted_event_inside_anchor_range_is_caught(app_env, client, batch, handler):
    _event(client, batch["id"], handler)
    anchor = client.post("/api/anchors").json()
    with app_env.Session() as db:
        db.execute(text("DELETE FROM events WHERE seq = 2"))
        db.commit()
    check = client.get(f"/api/anchors/{anchor['id']}/verify").json()
    assert check["events_match"] is False and check["events_found"] == 1


def test_database_url_is_pointed_at_psycopg():
    from app.database import _normalise_url

    assert _normalise_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert _normalise_url("postgresql://u:p@h/db?sslmode=require") == "postgresql+psycopg://u:p@h/db?sslmode=require"
    assert _normalise_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert _normalise_url("sqlite:///x.db") == "sqlite:///x.db"


def test_embedded_bytecode_matches_the_contract_source():
    from app import chain

    try:
        compiled = chain.compile_with_solc()
    except Exception:
        pytest.skip("solc 0.8.20 is not available offline")
    assert compiled == chain.CONTRACT_BYTECODE
