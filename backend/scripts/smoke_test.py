"""
End-to-end check of a running backend (local Docker or the deployed one):

    python scripts/smoke_test.py https://api.your-domain.com +15550001111 123456

Logs in with a TEST number (TEST_PHONE_NUMBERS on the server), adds a
contact, starts a check-in that ends in 5 seconds, waits for the Celery
worker to mark it missed and text the Circle, taps "I'm safe" (all-clear),
then deletes the test account again. Texts go to the fictional 555 number
+15550199999, so nobody real is texted.
"""

import sys
import time
from datetime import UTC, datetime, timedelta

import httpx

TEST_CONTACT = "+15550199999"


def main(base: str, phone: str, code: str) -> None:
    api = httpx.Client(base_url=base.rstrip("/"), timeout=30)

    def check(response: httpx.Response, expected: int = 200) -> dict:
        if response.status_code != expected:
            sys.exit(
                f"FAIL {response.request.method} {response.request.url}: "
                f"{response.status_code} {response.text}"
            )
        return response.json() if response.content else {}

    print("health:", check(api.get("/health")))
    tokens = check(api.post("/v1/auth/verify", json={"phone": phone, "code": code}))
    api.headers["Authorization"] = f"Bearer {tokens['access_token']}"
    print("logged in as", tokens["user"]["phone"])

    try:
        check(api.put("/v1/me", json={"display_name": "Smoke Test"}))
        check(api.post("/v1/contacts", json={"name": "Test", "phone": TEST_CONTACT}), 201)

        return_by = datetime.now(UTC) + timedelta(seconds=5)
        check_in = check(
            api.put(
                "/v1/check-ins/active",
                json={"return_by": return_by.isoformat(), "time_zone": "UTC"},
            )
        )
        print("check-in started, waiting for the worker…")

        deadline = time.time() + 120
        while True:
            status = check(api.get(f"/v1/check-ins/{check_in['id']}"))
            summary = status["alerts_summary"] or ""
            if status["status"] == "missed" and summary.startswith(("Texted", "No one")):
                break
            if time.time() > deadline:
                sys.exit(f"FAIL: check-in not alerted in time: {status}")
            time.sleep(2)
        late = time.time() - return_by.timestamp()
        print(f"missed and alerted {late:.0f}s after the return time: {summary}")

        safe = check(api.post(f"/v1/check-ins/{check_in['id']}/safe"))
        print("I'm safe ->", safe["result"], "| all-clear sending:", safe["all_clear_sending"])
        assert safe["result"] == "already_missed"

        history = check(api.get("/v1/history"))
        assert history[0]["status"] == "missed", history
        print("history ok")
    finally:
        check(api.delete("/v1/me"), 204)
        print("test account deleted")
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
