from __future__ import annotations

import io
import threading
from typing import Any

import qrcode
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from . import models, schemas
from .chain import chain_status, explorer_tx_url, submit_merkle_root
from .crypto_chain import (
    GENESIS_HASH,
    canonical_json,
    event_hash,
    generate_keypair,
    merkle_root,
    sign_message,
    verify_signature,
)
from .database import get_db
from .settings import settings

router = APIRouter(prefix="/api")
_event_lock = threading.Lock()


@router.get("/health", response_model=schemas.HealthOut)
def health():
    return schemas.HealthOut(status="ok", service="sikkim-provenance")


@router.get("/chain/status")
def get_chain_status():
    return chain_status()


@router.post("/participants", response_model=schemas.ParticipantOut)
def create_participant(body: schemas.ParticipantCreate, db: Session = Depends(get_db)):
    pub, priv = generate_keypair()
    row = models.Participant(
        name=body.name,
        role=body.role,
        public_key=pub,
        private_key_demo=priv,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/participants", response_model=list[schemas.ParticipantOut])
def list_participants(db: Session = Depends(get_db)):
    return db.scalars(select(models.Participant).order_by(models.Participant.created_at)).all()


@router.post("/batches", response_model=schemas.BatchOut)
def create_batch(body: schemas.BatchCreate, db: Session = Depends(get_db)):
    producer = db.get(models.Participant, body.producer_id)
    if not producer:
        raise HTTPException(404, "Producer not found")
    if producer.role != models.ParticipantRole.producer:
        raise HTTPException(400, "participant must have role=producer")

    batch = models.Batch(
        product_name=body.product_name,
        origin=body.origin,
        organic_claim=body.organic_claim,
        producer_id=producer.id,
    )
    db.add(batch)
    db.flush()

    details: dict[str, Any] = {
        "product_name": body.product_name,
        "origin": body.origin,
        "organic_claim": body.organic_claim,
    }
    if body.harvest_note:
        details["note"] = body.harvest_note

    _append_event(
        db,
        batch=batch,
        event_type=models.EventType.harvest,
        actor=producer,
        details=details,
        signature=None,
    )
    db.commit()
    return _load_batch(db, batch.id)


@router.get("/batches", response_model=list[schemas.BatchOut])
def list_batches(db: Session = Depends(get_db)):
    batches = db.scalars(select(models.Batch).order_by(models.Batch.created_at.desc())).all()
    return [_load_batch(db, b.id) for b in batches]


@router.get("/batches/{batch_id}", response_model=schemas.BatchOut)
def get_batch(batch_id: str, db: Session = Depends(get_db)):
    batch = _load_batch(db, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    return batch


@router.post("/batches/{batch_id}/events", response_model=schemas.EventOut)
def add_event(batch_id: str, body: schemas.EventCreate, db: Session = Depends(get_db)):
    batch = db.get(models.Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    actor = db.get(models.Participant, body.actor_id)
    if not actor:
        raise HTTPException(404, "Actor not found")
    if body.event_type == models.EventType.harvest:
        raise HTTPException(400, "harvest is created with the batch")

    event = _append_event(
        db,
        batch=batch,
        event_type=body.event_type,
        actor=actor,
        details=body.details,
        signature=body.signature,
    )
    db.commit()
    db.refresh(event)
    return event


@router.get("/batches/{batch_id}/verify", response_model=schemas.VerifyResult)
def verify_batch(batch_id: str, db: Session = Depends(get_db)):
    batch = db.get(models.Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    events = db.scalars(
        select(models.Event)
        .where(models.Event.batch_id == batch_id)
        .order_by(models.Event.seq)
    ).all()

    prev = GENESIS_HASH
    for ev in events:
        actor = db.get(models.Participant, ev.actor_id)
        if not actor or not verify_signature(actor.public_key, ev.payload_json, ev.signature):
            return schemas.VerifyResult(
                batch_id=batch_id,
                intact=False,
                event_count=len(events),
                broken_at_seq=ev.seq,
                message=f"Invalid signature at seq={ev.seq}",
            )
        expected = event_hash(prev, ev.payload_json, ev.signature)
        if expected != ev.hash or ev.prev_hash != prev:
            return schemas.VerifyResult(
                batch_id=batch_id,
                intact=False,
                event_count=len(events),
                broken_at_seq=ev.seq,
                message=f"Hash chain broken at seq={ev.seq}",
            )
        prev = ev.hash

    return schemas.VerifyResult(
        batch_id=batch_id,
        intact=True,
        event_count=len(events),
        message="Chain intact",
    )


@router.get("/batches/{batch_id}/qr")
def batch_qr(batch_id: str, db: Session = Depends(get_db)):
    if not db.get(models.Batch, batch_id):
        raise HTTPException(404, "Batch not found")
    payload = f"/trace/{batch_id}"
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@router.get("/anchors", response_model=list[schemas.AnchorOut])
def list_anchors(db: Session = Depends(get_db)):
    rows = db.scalars(select(models.Anchor).order_by(models.Anchor.id.desc())).all()
    cid = settings.anchor_chain_id if settings.rpc_configured else None
    return [_anchor_out(r, chain_id=cid) for r in rows]


@router.post("/anchors", response_model=schemas.AnchorOut)
def create_anchor(db: Session = Depends(get_db)):
    last = db.scalars(select(models.Anchor).order_by(models.Anchor.id.desc()).limit(1)).first()
    from_seq = (last.to_seq + 1) if last else 1

    max_seq = db.scalar(select(func.max(models.Event.seq))) or 0
    if max_seq < from_seq:
        raise HTTPException(400, "No new events to anchor")

    events = db.scalars(
        select(models.Event)
        .where(models.Event.seq >= from_seq, models.Event.seq <= max_seq)
        .order_by(models.Event.seq)
    ).all()
    root = merkle_root([e.hash for e in events])

    try:
        tx_hash, dry_run, chain_id = submit_merkle_root(root)
    except Exception as exc:
        raise HTTPException(502, f"Blockchain anchor failed: {exc}") from exc

    row = models.Anchor(
        merkle_root=root,
        from_seq=from_seq,
        to_seq=max_seq,
        tx_hash=tx_hash,
        dry_run=dry_run,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _anchor_out(row, chain_id=chain_id)


def _anchor_out(row: models.Anchor, chain_id: int | None = None) -> schemas.AnchorOut:
    return schemas.AnchorOut(
        id=row.id,
        merkle_root=row.merkle_root,
        from_seq=row.from_seq,
        to_seq=row.to_seq,
        tx_hash=row.tx_hash,
        dry_run=row.dry_run,
        anchored_at=row.anchored_at,
        explorer_url=explorer_tx_url(row.tx_hash, chain_id)
        if (not row.dry_run and chain_id is not None)
        else None,
    )


def _append_event(
    db: Session,
    *,
    batch: models.Batch,
    event_type: models.EventType,
    actor: models.Participant,
    details: dict[str, Any],
    signature: str | None,
) -> models.Event:
    with _event_lock:
        last_error: Exception | None = None
        batch_id = batch.id
        actor_id = actor.id
        for _ in range(8):
            try:
                with db.begin_nested():
                    last = db.scalars(
                        select(models.Event)
                        .where(models.Event.batch_id == batch_id)
                        .order_by(models.Event.seq.desc())
                        .limit(1)
                    ).first()
                    prev_hash = last.hash if last else GENESIS_HASH
                    next_seq = (db.scalar(select(func.max(models.Event.seq))) or 0) + 1

                    payload = {
                        "batch_id": batch_id,
                        "event_type": event_type.value,
                        "actor_id": actor_id,
                        "seq": next_seq,
                        "details": details,
                    }
                    payload_canonical = canonical_json(payload)

                    if signature:
                        if not verify_signature(actor.public_key, payload_canonical, signature):
                            raise HTTPException(400, "Invalid signature")
                        sig = signature
                    else:
                        if not actor.private_key_demo:
                            raise HTTPException(400, "No demo private key; provide signature")
                        sig = sign_message(actor.private_key_demo, payload_canonical)

                    h = event_hash(prev_hash, payload_canonical, sig)
                    event = models.Event(
                        batch_id=batch_id,
                        event_type=event_type,
                        actor_id=actor_id,
                        payload_json=payload_canonical,
                        prev_hash=prev_hash,
                        hash=h,
                        signature=sig,
                        seq=next_seq,
                    )
                    db.add(event)
                    db.flush()
                    return event
            except HTTPException:
                raise
            except IntegrityError as exc:
                last_error = exc
                actor = db.get(models.Participant, actor_id)
                if not actor:
                    raise HTTPException(404, "Actor missing after retry") from exc
                continue
        raise HTTPException(409, f"Could not allocate event seq: {last_error}")


def _load_batch(db: Session, batch_id: str) -> models.Batch | None:
    return db.scalars(
        select(models.Batch)
        .where(models.Batch.id == batch_id)
        .options(joinedload(models.Batch.events))
    ).first()
