"""Starting a session in plain words: the built-in reader, the Claude path and the endpoint."""

import json as jsonlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest

from app import plans
from app.config import get_settings

NY = ZoneInfo("America/New_York")
# A Tuesday evening in New York.
EVENING = datetime(2026, 10, 27, 18, 5, tzinfo=NY)


def read(text: str, now: datetime = EVENING) -> plans.Plan:
    return plans.read_plan(text, now, "America/New_York")


@pytest.mark.parametrize(
    ("text", "destination", "back_by"),
    [
        ("Date at Olive Garden on Main St, back by 11", "Olive Garden on Main St", "23:00"),
        ("Heading to the gym, home by 7:30pm", "gym", "19:30"),
        ("Walking to Sam's house until 9", "Sam's house", "21:00"),
        ("Run in the park for 45 min", None, "18:50"),
        ("Drinks at The Anchor for 2 hours", "The Anchor", "20:05"),
        ("Movie at AMC, back at midnight", "AMC", "00:00"),
    ],
)
def test_basic_reader(text, destination, back_by):
    plan = read(text)
    assert plan.source == "basic"
    assert plan.destination == destination
    assert plan.return_by is not None and plan.return_by.strftime("%H:%M") == back_by
    assert plan.problem is None


@pytest.mark.parametrize(
    ("text", "minutes"),
    [
        # The activity, then the trip back: both count.
        ("Have lunch at Olive Garden for an hour and be back in 30 minutes after lunch.", 90),
        ("Movie for 2 hours, takes 20 min to drive home", 140),
        ("Hike for an hour and a half", 90),
    ],
)
def test_basic_reader_adds_up_durations(text, minutes):
    plan = read(text)
    assert plan.return_by == EVENING + timedelta(minutes=minutes)


def test_basic_reader_morning_time_means_tomorrow():
    plan = read("Hiking at Bear Mountain, back by 8am tomorrow")
    assert plan.return_by == datetime(2026, 10, 28, 8, 0, tzinfo=NY)


def test_basic_reader_skips_a_time_only_minutes_away():
    # At 10:57 AM, "back by 11" means 11 PM, not in 5 minutes.
    plan = read("Dinner at Olive Garden, back by 11", datetime(2026, 10, 27, 10, 57, tzinfo=NY))
    assert plan.return_by == datetime(2026, 10, 27, 23, 0, tzinfo=NY)


def test_no_time_given():
    plan = read("Going to the library")
    assert plan.destination == "library"
    assert plan.return_by is None and "when you'll be back" in plan.problem


def test_too_soon_and_too_far():
    assert read("back in 2 min").problem == "That's less than 5 minutes from now."
    assert read("out for 30 hours").problem == "Pick a time within the next 24 hours."


def test_claude_fields_are_used(monkeypatch):
    seen = {}

    def fake_claude(text, now):
        seen["now"] = now
        return {
            "destination": "Olive Garden",
            "back_by_time": "22:45",
            "day": "today",
            "minutes_from_now": None,
        }

    monkeypatch.setattr(plans, "ask_claude", fake_claude)
    plan = plans.read_plan("dinner w/ Sam @ olive garden, home ~quarter to 11", EVENING, None)
    assert plan.source == "ai"
    assert plan.destination == "Olive Garden"
    assert plan.return_by == datetime(2026, 10, 27, 22, 45, tzinfo=NY)
    assert seen["now"].utcoffset() == timedelta(hours=-4)


def test_claude_not_used_without_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    assert plans.ask_claude("back by 11", EVENING) is None


def ollama_answers(monkeypatch, parts: dict) -> dict:
    """Pretend Ollama copied these parts out of the plan; returns what was sent to it."""
    sent: dict = {}

    def fake_post(url, json, timeout):
        sent.update(url=url, body=json)
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": jsonlib.dumps(parts)}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(get_settings(), "ai_provider", "ollama")
    monkeypatch.setattr(plans.httpx, "post", fake_post)
    return sent


def test_ollama_durations_are_added_up(monkeypatch):
    sent = ollama_answers(
        monkeypatch,
        {"destination": "Olive Garden", "back_by": None, "durations": [60, 30], "tomorrow": False},
    )
    plan = read("Lunch at Olive Garden for an hour, back in 30 minutes after")
    assert plan.source == "ai"
    assert plan.destination == "Olive Garden"
    assert plan.return_by == EVENING + timedelta(minutes=90)
    assert sent["url"] == "http://localhost:11434/api/chat"
    assert sent["body"]["model"] == "llama3.2"
    assert sent["body"]["format"] == plans.OLLAMA_SCHEMA


@pytest.mark.parametrize(
    ("text", "back_by", "tomorrow", "expected"),
    [
        # No am/pm: the next 11.
        ("Gym, back by 11", "11:00", False, datetime(2026, 10, 27, 23, 0, tzinfo=NY)),
        ("Gym, home by 7:30pm", "7:30pm", False, datetime(2026, 10, 27, 19, 30, tzinfo=NY)),
        ("Hike, back 8am tomorrow", "8:00am", True, datetime(2026, 10, 28, 8, 0, tzinfo=NY)),
        ("Bar, home at quarter to 11", "10:45", False, datetime(2026, 10, 27, 22, 45, tzinfo=NY)),
    ],
)
def test_ollama_clock_times(monkeypatch, text, back_by, tomorrow, expected):
    ollama_answers(
        monkeypatch,
        {"destination": "the gym", "back_by": back_by, "durations": [], "tomorrow": tomorrow},
    )
    assert read(text).return_by == expected


def test_time_the_ai_missed_comes_from_the_basic_reader(monkeypatch):
    ollama_answers(
        monkeypatch,
        {"destination": "Blue Bottle", "back_by": None, "durations": [], "tomorrow": False},
    )
    plan = read("Coffee at Blue Bottle, back around noon", datetime(2026, 10, 27, 9, 0, tzinfo=NY))
    assert plan.source == "ai"
    assert plan.destination == "Blue Bottle"
    assert plan.return_by == datetime(2026, 10, 27, 12, 0, tzinfo=NY)


def test_ollama_made_up_times_are_ignored(monkeypatch):
    # The model answered an hour and 9 pm, but the plan has neither.
    ollama_answers(
        monkeypatch,
        {"destination": "the library", "back_by": "9:00pm", "durations": [60], "tomorrow": False},
    )
    plan = read("Going to the library")
    assert plan.destination == "the library"
    assert plan.return_by is None and "when you'll be back" in plan.problem


def test_ollama_not_running_uses_basic_reader(monkeypatch):
    def refused(url, json, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(get_settings(), "ai_provider", "ollama")
    monkeypatch.setattr(plans.httpx, "post", refused)
    plan = read("Dinner at Olive Garden, back by 11")
    assert plan.source == "basic"
    assert plan.return_by == datetime(2026, 10, 27, 23, 0, tzinfo=NY)


def test_no_ai(monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_provider", "none")
    monkeypatch.setattr(plans, "ask_claude", lambda text, now: pytest.fail("Claude was asked"))
    assert read("Dinner at Olive Garden, back by 11").source == "basic"


def test_plan_endpoint(client, user):
    r = client.post(
        "/v1/check-ins/plan",
        json={
            "text": "Dinner at Olive Garden, back by 11",
            "now": EVENING.isoformat(),
            "time_zone": "America/New_York",
        },
        headers=user["headers"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["destination"] == "Olive Garden"
    assert datetime.fromisoformat(body["return_by"]) == datetime(2026, 10, 27, 23, 0, tzinfo=NY)
    assert body["source"] == "basic"

    # Nothing was started.
    assert client.get("/v1/history", headers=user["headers"]).json() == []


def test_plan_endpoint_needs_login(client):
    r = client.post("/v1/check-ins/plan", json={"text": "x", "now": EVENING.isoformat()})
    assert r.status_code == 401
