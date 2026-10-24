"""
Login codes: we text a 6-digit code, you type it in, you're logged in.

Codes live in Redis only, as a hash, for CODE_VALID_MINUTES, with a limited
number of tries. Test numbers (TEST_PHONE_NUMBERS) have a fixed code and are
never texted, which is how you test without paying for texts.
"""

import hashlib
import hmac
import secrets

from app import sms
from app.cache import get_redis, hit_rate_limit
from app.config import get_settings


class OtpError(Exception):
    """Something the person should be told, e.g. "Too many codes"."""


def _hash(phone: str, code: str) -> str:
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def send_code(phone: str) -> None:
    s = get_settings()
    if phone in s.test_codes():
        return

    if hit_rate_limit(f"otp-send:{phone}", s.max_codes_per_hour, 3600):
        raise OtpError("Too many codes requested. Please wait an hour and try again.")

    if sms.verify_enabled():
        result = sms.verify_send(phone)
        if not result.ok:
            raise OtpError(result.error or "Could not send the code")
        return

    code = f"{secrets.randbelow(1_000_000):06d}"
    r = get_redis()
    ttl = s.code_valid_minutes * 60
    r.set(f"otp:{phone}", _hash(phone, code), ex=ttl)
    r.delete(f"otp-tries:{phone}")
    result = sms.send_sms(
        phone,
        f"Your Androyit code is {code}. It expires in {s.code_valid_minutes} minutes. "
        "Don't share it with anyone.",
        use_trial_template=False,
    )
    if not result.ok:
        r.delete(f"otp:{phone}")
        raise OtpError(result.error or "Could not send the code")


def check_code(phone: str, code: str) -> bool:
    s = get_settings()
    fixed = s.test_codes().get(phone)
    if fixed is not None:
        return hmac.compare_digest(fixed, code)

    if sms.verify_enabled():
        return sms.verify_check(phone, code)

    r = get_redis()
    expected = r.get(f"otp:{phone}")
    if expected is None:
        raise OtpError('That code has expired. Tap "Send the code again".')

    tries = r.incr(f"otp-tries:{phone}")
    r.expire(f"otp-tries:{phone}", s.code_valid_minutes * 60)
    if tries > s.max_code_attempts:
        r.delete(f"otp:{phone}")
        raise OtpError('Too many wrong tries. Tap "Send the code again".')

    if not hmac.compare_digest(expected, _hash(phone, code)):
        return False
    r.delete(f"otp:{phone}", f"otp-tries:{phone}")  # each code works once
    return True
