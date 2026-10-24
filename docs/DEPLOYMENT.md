# Putting Reached live

## 1. The backend

Any Linux server (or VM) with Docker works. On it:

```bash
git clone https://github.com/chandanreddy04/Andrew114.git && cd Andrew114
cp backend/.env.example backend/.env
nano backend/.env          # see the checklist below
POSTGRES_PASSWORD='a-long-random-password' docker compose up -d --build
docker compose logs -f api worker beat
```

`backend/.env` checklist for production:

- `ENVIRONMENT=production` (the API refuses to start with weak settings)
- `JWT_SECRET`: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `SMS_BACKEND=twilio` and `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
  `TWILIO_FROM_NUMBER`
- `TEST_PHONE_NUMBERS=` empty (or only numbers you control)
- `BUGSNAG_API_KEY` from your Bugsnag project (Python platform)
- `CORS_ORIGINS`: only needed for the web preview; the phone app doesn't use CORS

Run exactly **one** `beat` container. You can run more `api` and `worker`
containers for capacity.

### HTTPS

Android blocks plain `http://` in release builds, so the API needs HTTPS.
The simplest way is Caddy in front of port 8000 (it gets certificates by
itself). `/etc/caddy/Caddyfile`:

```
api.your-domain.com {
    reverse_proxy localhost:8000
}
```

Managed hosts (Render, Railway, Fly.io, a cloud VM with a load balancer)
also work: run the same image three times with the commands from
`docker-compose.yml` (API, worker, beat) and point `DATABASE_URL` /
`REDIS_URL` at managed PostgreSQL and Redis.

### Backups

Everything important is in PostgreSQL. Redis only holds login codes, rate
limits, cached history and queued timers (timers are re-created by the
every-minute sweep, so losing Redis never loses an alert).

```bash
docker compose exec db pg_dump -U reached reached > backup.sql
```

### Database changes

Migrations run automatically when the API starts (`alembic upgrade head`).
After changing `app/models.py`, create one with:

```bash
cd backend && alembic revision --autogenerate -m "what changed"
```

## 2. Twilio

1. Buy a number that can send SMS to your users' countries, and put it in
   `TWILIO_FROM_NUMBER`.
2. Country rules: US numbers need A2P 10DLC registration (or a toll-free
   verification); India needs DLT registration and approved templates.
3. **Trial accounts** can't send custom text. Until upgrading, set
   `TWILIO_TRIAL_TEMPLATE=sms_account_alerts` so alert texts arrive as a
   Twilio sample, and log in with test numbers. After upgrading, clear
   `TWILIO_TRIAL_TEMPLATE`. No code change needed.
4. Optional: create a Twilio **Verify** service and set
   `TWILIO_VERIFY_SERVICE_SID` to let Twilio send and check login codes.

## 3. Bugsnag

- Backend: set `BUGSNAG_API_KEY`. The API, Celery worker and beat all report
  errors; phone numbers, codes and tokens are filtered out.
- App: crashes in installed builds are sent to `POST /v1/client-errors` and
  passed on to the same Bugsnag project (works in Expo Go too, no native
  module).

## 4. The Android app

```bash
cd mobile
npx eas-cli@latest init        # creates the EAS project (first time only)
npx eas-cli@latest env:create --name EXPO_PUBLIC_API_URL --value https://api.your-domain.com --environment preview --visibility plaintext
npx eas-cli@latest build --profile preview --platform android
```

The package name is `com.chandanreddy04.andrew114` (so it can be installed
next to the old Supabase build). Change it in `app.json` before the first
Play Store release; it can't change afterwards.

For instant updates (EAS Update) like the old app, run
`npx expo install expo-updates`, then `npx eas-cli@latest update:configure`,
and build again.
