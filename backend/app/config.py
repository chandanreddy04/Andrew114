"""
Settings, read from environment variables (or a .env file next to this
backend). See .env.example for every option and what it's for.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "development" or "production". Production refuses to start with the
    # example secret and turns off the console SMS backend.
    environment: str = "development"

    database_url: str = "postgresql+psycopg://reached:reached@localhost:5432/reached"
    redis_url: str = "redis://localhost:6379/0"

    # Signs the login tokens. MUST be a long random secret in production.
    jwt_secret: str = "change-me-in-production"
    access_token_minutes: int = 60
    refresh_token_days: int = 60

    # ----- Texting (Twilio) -----
    # "twilio" sends real texts. "console" only prints them in the server log
    # (handy on your laptop before Twilio is set up).
    sms_backend: str = "console"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    # Twilio TRIAL accounts can't send custom text, only Twilio's own sample
    # templates (e.g. "sms_account_alerts"). While this is set, that template
    # is sent instead of our message, to test that texts arrive. Clear it after
    # upgrading Twilio and the real messages are sent; no code change needed.
    twilio_trial_template: str = ""
    # Optional: send login codes with Twilio Verify instead of a plain text.
    twilio_verify_service_sid: str = ""

    # Fixed login codes for test numbers, e.g. "+15550001111=123456". No text
    # is sent to these numbers. Comma-separated for several.
    test_phone_numbers: str = ""

    # ----- Errors (Bugsnag) -----
    bugsnag_api_key: str = ""

    # Browsers allowed to call the API (the Expo web preview). "*" = any.
    cors_origins: str = "*"

    # The API's public address, used for the details link in alert texts
    # (e.g. https://reached-api.onrender.com). Empty = no link in texts.
    public_base_url: str = ""

    # ----- Address search (Start Session's "Where are you going?") -----
    # Photon: free OpenStreetMap search, no key needed. Any Photon-compatible
    # server works (e.g. a self-hosted one for heavy use).
    places_url: str = "https://photon.komoot.io/api/"

    # Session data (destination, photo, location) is deleted this many days
    # after a session ends; "Keep 7 more days" adds the same again.
    session_data_days: int = 7
    max_photo_bytes: int = 5 * 1024 * 1024

    # Limits
    max_sos_per_10_min: int = 3
    max_codes_per_hour: int = 5
    max_code_attempts: int = 5
    code_valid_minutes: int = 10

    # Test-only: run Celery tasks in-process instead of on a worker.
    celery_always_eager: bool = Field(default=False)

    @field_validator("database_url")
    @classmethod
    def _use_psycopg(cls, url: str) -> str:
        # Hosts (Render, Railway, Heroku…) hand out "postgres://…" URLs;
        # SQLAlchemy needs to be told to use the psycopg driver.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def test_codes(self) -> dict[str, str]:
        codes: dict[str, str] = {}
        for pair in self.test_phone_numbers.split(","):
            if "=" in pair:
                phone, code = pair.split("=", 1)
                codes[phone.strip()] = code.strip()
        return codes


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production:
        if settings.jwt_secret == "change-me-in-production" or len(settings.jwt_secret) < 32:
            raise RuntimeError("Set JWT_SECRET to a long random value in production.")
        if settings.sms_backend == "console":
            raise RuntimeError("SMS_BACKEND=console is not allowed in production.")
    return settings
