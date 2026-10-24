"""
Sending text messages with Twilio.

The Twilio password never leaves the server. Every function returns a result
instead of raising, so one failed text never stops the others.
"""

import logging
from dataclasses import dataclass, field

import httpx

from app.config import get_settings

log = logging.getLogger("reached.sms")

TWILIO_API = "https://api.twilio.com/2010-04-01"
VERIFY_API = "https://verify.twilio.com/v2"


@dataclass
class SmsResult:
    ok: bool
    error: str | None = None


@dataclass
class TextEveryoneResult:
    sent: int
    total: int
    errors: list[str] = field(default_factory=list)
    summary: str = ""


# Every text that was "sent" by the console backend (used by the tests).
console_outbox: list[tuple[str, str]] = []


def trial_template() -> str | None:
    return get_settings().twilio_trial_template or None


def send_sms(to: str, body: str, *, use_trial_template: bool = True) -> SmsResult:
    """use_trial_template=False for login codes: a sample text has no code in it."""
    s = get_settings()
    if s.sms_backend == "console":
        log.info("SMS to %s: %s", to, body)
        console_outbox.append((to, body))
        return SmsResult(ok=True)

    if not (s.twilio_account_sid and s.twilio_auth_token and s.twilio_from_number):
        return SmsResult(ok=False, error="Twilio is not set up")
    try:
        response = httpx.post(
            f"{TWILIO_API}/Accounts/{s.twilio_account_sid}/Messages.json",
            auth=(s.twilio_account_sid, s.twilio_auth_token),
            data={
                "To": to,
                "From": s.twilio_from_number,
                "Body": (use_trial_template and trial_template()) or body,
            },
            timeout=15,
        )
    except httpx.HTTPError as error:
        return SmsResult(ok=False, error=f"Network error: {error}")
    if response.is_success:
        return SmsResult(ok=True)
    try:
        message = response.json().get("message")
    except ValueError:
        message = None
    return SmsResult(ok=False, error=message or f"HTTP {response.status_code}")


def text_everyone(contacts: list[tuple[str, str]], message: str) -> TextEveryoneResult:
    """Text each (name, phone). Summary like "Texted 2 of 2 (Sam: …error…)"."""
    if not contacts:
        return TextEveryoneResult(sent=0, total=0, summary="No one in Circle")
    errors: list[str] = []
    sent = 0
    for name, phone in contacts:
        result = send_sms(phone, message)
        if result.ok:
            sent += 1
        else:
            errors.append(f"{name}: {result.error}")
    summary = (
        f"Texted {sent} of {len(contacts)}"
        + (" [trial template]" if trial_template() else "")
        + (f" ({'; '.join(errors)})" if errors else "")
    )
    return TextEveryoneResult(sent=sent, total=len(contacts), errors=errors, summary=summary)


# ----- Login codes with Twilio Verify (optional) -----
# When TWILIO_VERIFY_SERVICE_SID is set, Twilio creates, texts and checks the
# code. Otherwise the server makes its own code (see app/otp.py).


def verify_enabled() -> bool:
    s = get_settings()
    return s.sms_backend == "twilio" and bool(s.twilio_verify_service_sid)


def verify_send(phone: str) -> SmsResult:
    s = get_settings()
    try:
        response = httpx.post(
            f"{VERIFY_API}/Services/{s.twilio_verify_service_sid}/Verifications",
            auth=(s.twilio_account_sid, s.twilio_auth_token),
            data={"To": phone, "Channel": "sms"},
            timeout=15,
        )
    except httpx.HTTPError as error:
        return SmsResult(ok=False, error=f"Network error: {error}")
    if response.is_success:
        return SmsResult(ok=True)
    return SmsResult(ok=False, error=response.json().get("message", f"HTTP {response.status_code}"))


def verify_check(phone: str, code: str) -> bool:
    s = get_settings()
    try:
        response = httpx.post(
            f"{VERIFY_API}/Services/{s.twilio_verify_service_sid}/VerificationCheck",
            auth=(s.twilio_account_sid, s.twilio_auth_token),
            data={"To": phone, "Code": code},
            timeout=15,
        )
    except httpx.HTTPError:
        return False
    return response.is_success and response.json().get("status") == "approved"
