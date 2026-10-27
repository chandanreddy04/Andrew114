"""The shapes of what the API accepts and returns (checked automatically)."""

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# "+" then 8 to 15 digits, not starting with 0: +15551234567, +919876543210.
PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone(value: str) -> str:
    """ "+1 (555) 123-4567" -> "+15551234567"; rejects anything else."""
    phone = re.sub(r"[\s\-().]", "", value)
    if not PHONE_RE.match(phone):
        raise ValueError("Use + and the country code, e.g. +15551234567")
    return phone


class PhoneIn(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        return normalize_phone(value)


class VerifyIn(PhoneIn):
    code: str = Field(pattern=r"^\d{4,8}$")


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=200)


class UserOut(BaseModel):
    id: uuid.UUID
    phone: str
    display_name: str | None
    # When the profile picture last changed (null = none). Also tells the app
    # when its saved copy is out of date.
    photo_updated_at: datetime | None = None


class TokensOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until the access token expires
    user: UserOut


class ProfileIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)

    @field_validator("display_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name can't be empty")
        return value


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name can't be empty")
        return value

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        return normalize_phone(value)


class ContactOut(BaseModel):
    id: uuid.UUID
    name: str
    phone: str


class CheckInIn(BaseModel):
    return_by: datetime
    # e.g. "America/New_York"; texts to your Circle show your local time.
    time_zone: str | None = Field(default=None, max_length=64)
    # Left out = keep what the active check-in already has (e.g. the Home
    # screen's +30m only moves the time).
    destination: str | None = Field(default=None, max_length=255)
    # Set when the destination was picked from the address search (sent with
    # destination; a typed destination has none).
    destination_latitude: float | None = Field(default=None, ge=-90, le=90)
    destination_longitude: float | None = Field(default=None, ge=-180, le=180)
    share_location: bool | None = None

    @field_validator("destination")
    @classmethod
    def _strip_destination(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        return value or None


class PlaceOut(BaseModel):
    """One address search result, e.g. "Olive Garden" / "2001 S Lamar Blvd, Austin, TX"."""

    name: str
    address: str
    # Google results come without a position: ask GET /v1/places/{place_id}
    # for it once one is picked.
    latitude: float | None = None
    longitude: float | None = None
    place_id: str | None = None
    # Who the result is from, for the credit under the list.
    source: Literal["google", "tomtom", "openstreetmap"] = "openstreetmap"


class MapPreviewOut(BaseModel):
    # The map as a data: URL ("data:image/jpeg;base64,…"), ready for an <Image>.
    image: str


class LocationIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, ge=0, le=100_000)


class CheckInStartedOut(BaseModel):
    id: uuid.UUID
    status: str


class CheckInStatusOut(BaseModel):
    id: uuid.UUID
    status: Literal["active", "safe", "missed"]
    return_by: datetime
    alerts_sent_at: datetime | None
    alerts_summary: str | None
    destination: str | None = None
    destination_latitude: float | None = None
    destination_longitude: float | None = None
    share_location: bool = True
    has_location: bool = False
    has_photo: bool = False


class ConfirmSafeOut(BaseModel):
    # "safe": ended in time, nobody alerted.
    # "already_missed": the server had already marked it missed.
    result: Literal["safe", "already_missed"]
    alerts_sent_at: datetime | None = None
    alerts_summary: str | None = None
    alerts_sent_count: int | None = None
    # Your Circle was alerted, so they're now being texted that you're safe.
    all_clear_sending: bool = False


class SosIn(BaseModel):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, ge=0, le=100_000)
    battery_level: int | None = Field(default=None, ge=0, le=100)


class SosOut(BaseModel):
    id: uuid.UUID
    sent: int
    total: int
    errors: list[str]
    # Twilio is on a trial account, so a generic sample text was sent instead.
    trial_template: bool


class HistoryCheckIn(BaseModel):
    kind: Literal["check-in"] = "check-in"
    id: uuid.UUID
    destination: str | None = None
    has_photo: bool = False
    # When this session's data will be deleted (null while it's still going).
    delete_after: datetime | None = None
    at: datetime
    return_by: datetime
    status: Literal["active", "safe", "missed"]
    ended_at: datetime | None
    alerts_summary: str | None
    confirmed_safe_at: datetime | None
    all_clear_summary: str | None


class KeepOut(BaseModel):
    delete_after: datetime


class SosSafeOut(BaseModel):
    # Your Circle was texted about the SOS, so they're now told you're safe.
    all_clear_sent: bool
    all_clear_summary: str | None


class HistorySos(BaseModel):
    kind: Literal["sos"] = "sos"
    at: datetime
    alerts_summary: str | None
    had_location: bool


class ClientErrorIn(BaseModel):
    message: str = Field(max_length=2000)
    stack: str | None = Field(default=None, max_length=20_000)
    is_fatal: bool = False
    app_version: str | None = Field(default=None, max_length=100)
    platform: str | None = Field(default=None, max_length=20)
