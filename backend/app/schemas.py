from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .models import EventType, ParticipantRole


class ParticipantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: ParticipantRole


class ParticipantOut(BaseModel):
    id: str
    name: str
    role: ParticipantRole
    public_key: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BatchCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=200)
    origin: str = Field(min_length=1, max_length=200)
    organic_claim: bool = True
    producer_id: str
    harvest_note: str | None = None


class EventCreate(BaseModel):
    event_type: EventType
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    signature: str | None = None


class EventOut(BaseModel):
    id: str
    batch_id: str
    event_type: EventType
    actor_id: str
    payload_json: str
    prev_hash: str
    hash: str
    signature: str
    seq: int
    created_at: datetime

    model_config = {"from_attributes": True}


class BatchOut(BaseModel):
    id: str
    product_name: str
    origin: str
    organic_claim: bool
    producer_id: str
    created_at: datetime
    events: list[EventOut] = []

    model_config = {"from_attributes": True}


class VerifyResult(BaseModel):
    batch_id: str
    intact: bool
    event_count: int
    broken_at_seq: int | None = None
    message: str


class AnchorOut(BaseModel):
    id: int
    merkle_root: str
    from_seq: int
    to_seq: int
    tx_hash: str | None
    dry_run: bool
    anchored_at: datetime
    explorer_url: str | None = None

    model_config = {"from_attributes": True}


class HealthOut(BaseModel):
    status: str
    service: str
