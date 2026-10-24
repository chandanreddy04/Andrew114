"""
The database tables.

Every row belongs to one user (user_id) and is deleted with them ("on delete
cascade"), so deleting an account removes everything stored about it. The API
only ever reads or changes the signed-in user's own rows (see app/deps.py).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    TypeDecorator,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """A timestamp that always comes back as UTC-aware (SQLite drops the zone)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Full international format, e.g. +15551234567. This is the login.
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    # Your name, used in texts to your Circle ("Alex hasn't checked in").
    display_name: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class RefreshToken(Base):
    """One per logged-in phone. Logging out deletes it, so it can't be reused."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Only a hash is stored: a leaked database can't be used to log in.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Contact(Base):
    """A person in your Circle of Trust."""

    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint("length(name) between 1 and 100", name="contacts_name_length"),
        CheckConstraint("length(phone) between 3 and 30", name="contacts_phone_length"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="contacts")


class CheckIn(Base):
    """
    A check-in ("session"). status goes:
      'active' -> 'safe'   (you tapped "I'm safe" in time)
               -> 'missed' (the server noticed you didn't, and texted your Circle)
    """

    __tablename__ = "check_ins"
    __table_args__ = (
        CheckConstraint("status in ('active', 'safe', 'missed')", name="check_ins_status"),
        # Each person can only have one active check-in at a time.
        Index(
            "check_ins_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
        # Helps the every-minute checker find overdue check-ins quickly.
        Index(
            "check_ins_active_return_by",
            "return_by",
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    return_by: Mapped[datetime] = mapped_column(UTCDateTime)
    # Your time zone (e.g. "America/New_York"), so texts show your local time.
    time_zone: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(10), default="active")
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)  # tapped "I'm safe"
    missed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)  # server marked missed

    # Missed-check-in texts: when, what happened ("Texted 2 of 2"), and how
    # many were delivered (so we only send an "all clear" if someone got one).
    alerts_sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    alerts_summary: Mapped[str | None] = mapped_column(Text)
    alerts_sent_count: Mapped[int | None] = mapped_column(Integer)

    # Tapped "I'm safe" after it was already missed, and the "all clear" texts.
    confirmed_safe_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    all_clear_sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    all_clear_summary: Mapped[str | None] = mapped_column(Text)

    # ----- Shared with your Circle only if an alert triggers -----
    # Where you said you're going, e.g. "Central Park".
    destination: Mapped[str | None] = mapped_column(String(120))
    # Whether your last known location may be shared (the "Location" switch).
    share_location: Mapped[bool] = mapped_column(Boolean, default=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    accuracy_meters: Mapped[float | None] = mapped_column(Float)
    location_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Unguessable link for your Circle's details page (/s/<token>), which only
    # works once the check-in was missed.
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)

    # Session data is deleted at this time: 7 days after the session ends,
    # later if you tap "Keep 7 more days" in Session History.
    delete_after: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)


class SessionPhoto(Base):
    """The outfit photo for a check-in (deleted with it)."""

    __tablename__ = "session_photos"

    check_in_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("check_ins.id", ondelete="CASCADE"), primary_key=True
    )
    content_type: Mapped[str] = mapped_column(String(30))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class SosEvent(Base):
    """Each time someone presses SOS."""

    __tablename__ = "sos_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    # Empty if location wasn't available.
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    accuracy_meters: Mapped[float | None] = mapped_column(Float)
    alerts_sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    alerts_summary: Mapped[str | None] = mapped_column(Text)
