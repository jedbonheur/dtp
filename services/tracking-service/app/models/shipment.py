import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Float, DateTime, Text, JSON, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


# ──────────────────────────────────────────────────────────
# WHY AN ENUM?
# Instead of storing raw strings like "pending" or "PENDING"
# or "Pending" — an Enum forces ONE valid set of values.
# The database will REJECT anything not in this list.
# ──────────────────────────────────────────────────────────
class ShipmentStatus(str, PyEnum):
    PENDING    = "pending"
    ASSIGNED   = "assigned"
    IN_TRANSIT = "in_transit"
    DELIVERED  = "delivered"
    FAILED     = "failed"
    CANCELLED  = "cancelled"


# ──────────────────────────────────────────────────────────
# SHIPMENT — the CURRENT STATE of a delivery
# Answers: "what is this shipment right now?"
# ──────────────────────────────────────────────────────────
class Shipment(Base):
    __tablename__ = "shipments"

    # UUID instead of integer ID
    # WHY: integers are guessable → users can try /shipments/1, /shipments/2
    # UUID like 550e8400-e29b-41d4-a716-446655440000 is impossible to guess
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4      # auto-generate on creation
    )

    # WHO created this shipment — comes from JWT (X-User-ID header)
    # index=True because we query "show me shipments by this user" constantly
    created_by: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False
    )

    # CURRENT status — indexed because we filter by status constantly
    # e.g. "show all pending shipments" → WHERE status = 'pending'
    status: Mapped[str] = mapped_column(
        String(50),
        default=ShipmentStatus.PENDING,
        index=True,
        nullable=False
    )


    # nullable=True because shipment starts unassigned
    # index=True because drivers query "show MY deliveries" constantly
    assigned_driver_id: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
        nullable=True
    )

    # ── SENDER ──────────────────────────────────────────
    # WHY flat columns and not JSON?
    # Flat = queryable:  WHERE sender_email = 'john@x.com'  ✅
    # JSON = NOT queryable inside the blob                  ❌
    sender_name:    Mapped[str] = mapped_column(String(255), nullable=False)
    sender_email:   Mapped[str] = mapped_column(String(255), nullable=False)
    sender_phone:   Mapped[str] = mapped_column(String(20),  nullable=False)
    sender_address: Mapped[str] = mapped_column(String(500), nullable=False)

    # ── RECIPIENT ────────────────────────────────────────
    recipient_name:    Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_email:   Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_phone:   Mapped[str] = mapped_column(String(20),  nullable=False)
    recipient_address: Mapped[str] = mapped_column(String(500), nullable=False)

    # ── PACKAGE ──────────────────────────────────────────
    description: Mapped[str]         = mapped_column(Text,         nullable=False)
    weight_kg:   Mapped[float | None] = mapped_column(Float,       nullable=True)
    priority:    Mapped[str]          = mapped_column(String(50),   default="standard")

    # WHY JSON here (but not for sender/recipient)?
    # We never query INSIDE dimensions — we just store and return it
    # {length: 35, width: 25, height: 5} stays together as a blob
    dimensions_cm: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── LIVE LOCATION ────────────────────────────────────
    # Updated by driver as they move — starts null
    current_latitude:            Mapped[float | None]    = mapped_column(Float,    nullable=True)
    current_longitude:           Mapped[float | None]    = mapped_column(Float,    nullable=True)
    current_location_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── TIMING ───────────────────────────────────────────
    estimated_delivery: Mapped[datetime | None] = mapped_column(DateTime,    nullable=True)
    created_at:         Mapped[datetime]        = mapped_column(DateTime,    default=datetime.utcnow, index=True)
    updated_at:         Mapped[datetime | None] = mapped_column(DateTime,    nullable=True)
    updated_by:         Mapped[str | None]      = mapped_column(String(255), nullable=True)

    # ── VIRTUAL PROPERTIES (for Pydantic serialisation) ──
    # ShipmentResponse expects nested sender/recipient/package objects.
    # These properties assemble them from the flat columns so that
    # ShipmentResponse.from_orm(shipment) works without any changes to
    # the schema or the routes.

    @property
    def sender(self) -> dict:
        return {
            "name": self.sender_name,
            "email": self.sender_email,
            "phone": self.sender_phone,
            "address": self.sender_address,
        }

    @property
    def recipient(self) -> dict:
        return {
            "name": self.recipient_name,
            "email": self.recipient_email,
            "phone": self.recipient_phone,
            "address": self.recipient_address,
        }

    @property
    def package(self) -> dict:
        return {
            "description": self.description,
            "weight_kg": self.weight_kg,
            "dimensions_cm": self.dimensions_cm,
        }

    # ── RELATIONSHIP ──────────────────────────────────────
    # This is NOT a database column — it's a SQLAlchemy instruction:
    # "when I load a Shipment, also load its ShipmentEvents"
    #
    # cascade="all, delete-orphan"
    # → if Shipment is deleted, ALL its events are deleted too
    # → no orphan rows left behind in shipment_events
    #
    # lazy="joined"
    # → loads events in the SAME SQL query as the shipment
    # → ONE query instead of: 1 query for shipment + N queries for events
    # → this is called avoiding the N+1 problem
    #
    # order_by="ShipmentEvent.timestamp"
    # → events always come back oldest first (chronological timeline)
    events: Mapped[list["ShipmentEvent"]] = relationship(
        "ShipmentEvent",
        back_populates="shipment",
        cascade="all, delete-orphan",
        lazy="joined",
        order_by="ShipmentEvent.timestamp"
    )


# ──────────────────────────────────────────────────────────
# SHIPMENT EVENT — the HISTORY of a delivery
# Answers: "what happened to this shipment over time?"
#
# GOLDEN RULE: We NEVER update or delete rows here.
# Only INSERT new events. This is an immutable audit log.
# Think of it like git commits — history is permanent.
# ──────────────────────────────────────────────────────────
class ShipmentEvent(Base):
    __tablename__ = "shipment_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Links this event to its parent Shipment
    # index=True because we always query "give me ALL events for shipment X"
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id"),     # ← tells DB this references shipments.id
        nullable=False,
        index=True
    )

    # What type of event? One of:
    # "shipment_created", "shipment_assigned",
    # "location_updated", "status_changed", "delivery_completed"
    event_type:  Mapped[str]      = mapped_column(String(50),  index=True,  nullable=False)
    timestamp:   Mapped[datetime] = mapped_column(DateTime,    default=datetime.utcnow, index=True)
    description: Mapped[str]      = mapped_column(String(500), nullable=False)

    # WHO triggered this event + their role
    # Critical for audit trail:
    # "admin_42 changed status to DELIVERED at 14:30 on 2026-02-25"
    triggered_by_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    triggered_by_role:    Mapped[str] = mapped_column(String(50),  nullable=False)

    # Flexible extra data — varies by event type
    # location_updated → {"lat": 40.7, "lng": -74.0, "speed_kmh": 45}
    # shipment_assigned → {"driver_name": "John", "estimated_delivery": "..."}
    # We use JSON here because the shape changes per event type
    event_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Back-reference to parent Shipment
    # back_populates="events" must match the name in Shipment.events above
    shipment: Mapped["Shipment"] = relationship(
        "Shipment",
        back_populates="events"
    )