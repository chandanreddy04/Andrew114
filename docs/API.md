# Reached API reference

Base URL: `EXPO_PUBLIC_API_URL` in the app (e.g. `https://api.example.com`).
All bodies are JSON. Interactive docs: `GET /docs` (development only).

Logged-in requests send `Authorization: Bearer <access_token>`. Errors look
like `{"detail": "message"}` (or a list of field errors for invalid input).

## Auth

| Method | Path                  | Body                    | Returns |
| ------ | --------------------- | ----------------------- | ------- |
| POST   | `/v1/auth/send-code`  | `{phone}`               | 204. 429 if too many codes (5/hour/number) |
| POST   | `/v1/auth/verify`     | `{phone, code}`         | `{access_token, refresh_token, expires_in, user}`; first login creates the account |
| POST   | `/v1/auth/refresh`    | `{refresh_token}`       | a new pair; the old refresh token stops working |
| POST   | `/v1/auth/logout`     | `{refresh_token}`       | 204 |

Phones are full international format; spaces, dashes and brackets are
removed (`+1 (555) 123-4567` → `+15551234567`).

## Account

| Method | Path     | Body              | Returns |
| ------ | -------- | ----------------- | ------- |
| GET    | `/v1/me` |                   | `{id, phone, display_name}` |
| PUT    | `/v1/me` | `{display_name}`  | the same |
| DELETE | `/v1/me` |                   | 204; deletes Circle, sessions, SOS history and logins |

## Circle

| Method | Path                 | Body            | Returns |
| ------ | -------------------- | --------------- | ------- |
| GET    | `/v1/contacts`       |                 | `[{id, name, phone}]` oldest first |
| POST   | `/v1/contacts`       | `{name, phone}` | 201 contact. 409 duplicate number, 400 your own number |
| PUT    | `/v1/contacts/{id}`  | `{name, phone}` | contact |
| DELETE | `/v1/contacts/{id}`  |                 | 204 |

## Sessions (check-ins)

| Method | Path                          | Body                        | Returns |
| ------ | ----------------------------- | --------------------------- | ------- |
| PUT    | `/v1/check-ins/active`        | `{return_by, time_zone?}`   | `{id, status}`: starts one, or moves the active one's time |
| GET    | `/v1/check-ins/{id}`          |                             | `{id, status, return_by, alerts_sent_at, alerts_summary}` |
| POST   | `/v1/check-ins/{id}/safe`     |                             | `{result: "safe" \| "already_missed", alerts_summary, alerts_sent_at, alerts_sent_count, all_clear_sending}` |

`return_by` is an ISO time with a zone, in the future, at most 7 days ahead.
`status` is `active`, `safe` or `missed`.

## SOS

| Method | Path      | Body                                          | Returns |
| ------ | --------- | --------------------------------------------- | ------- |
| POST   | `/v1/sos` | `{latitude?, longitude?, accuracy_meters?}`   | `{sent, total, errors, trial_template}`. 429 after 3 in 10 minutes |

## History

`GET /v1/history?limit=20` (1–100): newest first, mixed:

```json
[
  {"kind": "check-in", "at": "…", "return_by": "…", "status": "missed",
   "ended_at": null, "alerts_summary": "Texted 2 of 2",
   "confirmed_safe_at": "…", "all_clear_summary": "Texted 2 of 2"},
  {"kind": "sos", "at": "…", "alerts_summary": "Texted 1 of 1", "had_location": true}
]
```

## Other

- `POST /v1/client-errors` `{message, stack?, is_fatal, app_version?, platform?}` → 204 (forwarded to Bugsnag)
- `GET /health` → `{status, database, redis}`
