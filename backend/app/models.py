import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ParticipantRole(str, enum.Enum):
    producer = "producer"
    handler = "handler"
    retailer = "retailer"
    regulator = "regulator"


class EventType(str, enum.Enum):
    harvest = "harvest"
    handoff = "handoff"
    process = "process"
    ship = "ship"
    retail = "retail"


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[ParticipantRole] = mapped_column(Enum(ParticipantRole), nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    private_key_demo: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    batches = relationship("Batch", back_populates="producer")
    events = relationship("Event", back_populates="actor")


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    origin: Mapped[str] = mapped_column(String(200), nullable=False)
    organic_claim: Mapped[bool] = mapped_column(Boolean, default=True)
    producer_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    producer = relationship("Participant", back_populates="batches")
    events = relationship("Event", back_populates="batch", order_by="Event.created_at")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("seq", name="uq_events_seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), nullable=False, index=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    actor_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    batch = relationship("Batch", back_populates="events")
    actor = relationship("Participant", back_populates="events")


class Anchor(Base):
    __tablename__ = "anchors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merkle_root: Mapped[str] = mapped_column(String(66), nullable=False)
    from_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    to_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    anchored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
