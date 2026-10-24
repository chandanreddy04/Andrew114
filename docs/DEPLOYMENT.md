# Putting Reached live

## 0. Try it on your phone today (no hosting needed)

The test APK (EAS profile `preview`) talks to the backend on your laptop
over Wi-Fi at `http://192.168.1.245:8000`.

1. On the laptop: `cd backend && .venv\Scripts\python scripts\dev_server.py`.
   If Windows asks whether Python may use the network, allow **Private
   networks**.
2. Phone on the same Wi-Fi: install the APK from the EAS build page, open it,
   log in with **+15550001111** / **123456**.
3. Texts are printed in the laptop's terminal (nobody is really texted).

If the laptop's Wi-Fi address changes (check with `ipconfig`), point the app
at the new one without rebuilding:

```bash
cd mobile
npx eas-cli@latest env:update --variable-name EXPO_PUBLIC_API_URL --value http://NEW-IP:8000 --environment preview
npx eas-cli@latest update --channel preview --environment preview --platform android --message "New API address"
```

Close and reopen the app twice to pick up the update.

## 1. The backend

### Option A: Render (easiest, everything managed)

`render.yaml` in this repo describes the whole backend. In the Render
dashboard: **New → Blueprint →** pick `chandanreddy04/Andrew114` → fill in
the Twilio and Bugsnag values it asks for → **Apply**. It creates:

| Piece              | Render plan     | About   |
| ------------------ | --------------- | ------- |
| `reached-api`      | Starter         | $7/mo   |
| `reached-worker`   | Starter         | $7/mo   |
| `reached-db`       | Basic 256 MB    | ~$6/mo  |
| `reached-redis`    | Free            | $0      |

(Prices as listed by Render; check before applying.) Don't put the API or
worker on the free plan: free services fall asleep, and the worker is what
sends missed-check-in texts. The API URL will be like
`https://reached-api.onrender.com`. Check it with:

```bash
cd backend && .venv\Scripts\python scripts\smoke_test.py https://reached-api.onrender.com +15550001111 123456
```

Then point the app at it (section 4).

### Option B: your own server with Docker

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

The EAS project is `@chandanreddy04/andrew114`, with EAS Update (instant
updates) on the `preview` and `production` channels. The API address is the
EAS environment variable `EXPO_PUBLIC_API_URL`.

Once the backend is hosted, switch the test app to it without rebuilding:

```bash
cd mobile
npx eas-cli@latest env:update --variable-name EXPO_PUBLIC_API_URL --value https://reached-api.onrender.com --environment preview
npx eas-cli@latest update --channel preview --environment preview --platform android --message "Use hosted API"
```

For a release build:

```bash
npx eas-cli@latest env:create --name EXPO_PUBLIC_API_URL --value https://reached-api.onrender.com --environment production --visibility plaintext
npx eas-cli@latest build --profile production --platform android
```

Test (`preview`) builds may use plain `http://` (for the laptop); production
builds only allow HTTPS (`app.config.js`, `ALLOW_HTTP_API` in `eas.json`).

The package name is `com.chandanreddy04.andrew114` (so it can be installed
next to the old Supabase build). Change it in `app.json` before the first
Play Store release; it can't change afterwards.
