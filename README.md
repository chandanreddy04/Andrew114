# Androyit (custom backend edition of Reached)

Androyit (formerly Reached) is a personal-safety check-in app. Before you go out you set a time
you expect to be back. If you don't tap **"I'm safe"** by then, your **Circle
of Trust** (people you choose, who don't need the app) get a text. There's
also an **SOS** button that texts your Circle your location straight away.

This repo has the same app, features and privacy rules as the earlier
Supabase version (`chandanreddy04/reached`), rebuilt on our own backend:

```
 ┌────────────────┐    HTTP/JSON     ┌──────────────────────┐
 │  Mobile app    │ ───────────────▶ │  Backend API         │
 │  (Expo / RN)   │ ◀─────────────── │  (FastAPI / Python)  │
 └────────────────┘                  └──────────┬───────────┘
                                                │
        ┌──────────────┬─────────────┬──────────┼───────────┬─────────────┐
        ▼              ▼             ▼          ▼           ▼
   PostgreSQL        Redis        Celery      Twilio      Bugsnag
     (data)        (cache,      (timers /   (SMS / OTP)   (errors)
                 codes, limits)   alerts)
```

| Folder              | What it is                                              |
| ------------------- | ------------------------------------------------------- |
| `mobile/`           | The Android app (Expo SDK 57, React Native, Expo Router) |
| `backend/`          | The API, database migrations, Celery worker, tests      |
| `docker-compose.yml`| Runs the whole backend (API, worker, beat, Postgres, Redis) |
| `docs/`             | API reference and how things work                       |

## Features (same as the Supabase app)

- **Phone-number login** with a 6-digit texted code, plus consent to texts.
- **Welcome screens** the first time on a phone.
- **Circle of Trust**: add, edit, remove people; import from the phone's
  contacts (one picked person only); duplicate and own-number checks.
- **Sessions (check-ins)**: pick a duration, see a live countdown, +15/+30/+1 hr
  extend, change the return time, "I'm safe".
- **Server-side watching**: the server texts your Circle if you miss your
  time, even if your phone is off. Tapping "I'm safe" after that sends an
  **all-clear** text (only if an alert was actually delivered).
- **SOS**: texts everyone your location (Google Maps link) or says it's
  unavailable. Limited to 3 per 10 minutes.
- **Local reminders** on the phone 10 minutes before (or halfway through
  short sessions) and at the return time.
- **History / Notifications**: past sessions and SOS alerts with outcomes.
- **Settings**: account, log out (blocked during an active session), delete
  account (asks twice; deletes everything on the server), version info.
- Privacy: location only when you press SOS, no background tracking, no
  address-book upload, login tokens in the phone's secure storage.

## Quick start (laptop, no Docker needed)

On Windows, just double-click **`start-backend.bat`** in this folder (keep
its window open while testing; close it to stop). Or by hand:

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # macOS/Linux: .venv/bin/pip
.venv/Scripts/python scripts/dev_server.py
```

That starts the API on http://localhost:8000 (docs at `/docs`) with a local
SQLite file and an in-memory Redis, and prints texts in the terminal instead
of sending them. Log in with the test number **+15550001111**, code **123456**.

Then the app:

```bash
cd mobile
npm install
cp .env.example .env.local      # set EXPO_PUBLIC_API_URL
npx expo start
```

Open it in Expo Go on your Android phone (phone and laptop on the same Wi-Fi,
`EXPO_PUBLIC_API_URL=http://<laptop IP>:8000`), or press `a` for the emulator
(`http://10.0.2.2:8000`).

## Running the real backend (Docker)

```bash
cp backend/.env.example backend/.env    # fill in secrets
docker compose up --build
```

This runs PostgreSQL, Redis, the API (applies migrations on start), the
Celery worker and Celery beat. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
for putting it on a server with HTTPS, and for Twilio and Bugsnag.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest -q
cd mobile && npx tsc --noEmit && npx expo lint
```

## Twilio trial accounts

While Twilio is on a trial account it can't send custom text. Set
`TWILIO_TRIAL_TEMPLATE` (e.g. `sms_account_alerts`) and alert texts are sent
as that Twilio sample instead, so you can see that they arrive. After
upgrading Twilio, clear it; no code change needed. Login codes can't be sent
as a sample (they'd have no code in them): use test numbers
(`TEST_PHONE_NUMBERS`) or a Twilio Verify service until then.
