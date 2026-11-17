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


def test_ollama_made_up_place_and_am_pm_are_ignored(monkeypatch):
    # The model answered a place from its prompt and an "am" the plan doesn't say.
    ollama_answers(
        monkeypatch,
        {"destination": "Joe's Pizza", "back_by": "9:00am", "durations": [], "tomorrow": False},
    )
    plan = read("Walking around, back by 9 or so")
    assert plan.destination is None
    assert plan.return_by == datetime(2026, 10, 27, 21, 0, tzinfo=NY)


def test_basic_time_wins_over_ollama(monkeypatch):
    # "a few hours" is 3 hours; the model said 2.
    ollama_answers(
        monkeypatch,
        {"destination": "the mall", "back_by": None, "durations": [120], "tomorrow": False},
    )
    plan = read("Shopping at the mall for a few hours")
    assert plan.destination == "the mall"
    assert plan.return_by == EVENING + timedelta(hours=3)


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
    assert body["choices"] == []


def test_plan_endpoint_offers_am_or_pm(client, user):
    r = client.post(
        "/v1/check-ins/plan",
        json={
            "text": "Coffee at Blue Bottle, back by 11",
            "now": MORNING.isoformat(),
            "time_zone": "America/New_York",
        },
        headers=user["headers"],
    )
    body = r.json()
    assert body["return_by"] is None
    assert body["problem"] == "Did you mean 11:00 AM or 11:00 PM?"
    assert [datetime.fromisoformat(c) for c in body["choices"]] == [
        datetime(2026, 10, 27, 11, 0, tzinfo=NY),
        datetime(2026, 10, 27, 23, 0, tzinfo=NY),
    ]


# ----- AM or PM, time phrases, places -----

MORNING = datetime(2026, 10, 27, 10, 30, tzinfo=NY)


def test_am_or_pm_is_asked_when_both_are_likely():
    plan = read("Coffee at Blue Bottle, back by 11", MORNING)
    assert plan.return_by is None
    assert plan.choices == [
        datetime(2026, 10, 27, 11, 0, tzinfo=NY),
        datetime(2026, 10, 27, 23, 0, tzinfo=NY),
    ]


@pytest.mark.parametrize(
    ("text", "now", "expected"),
    [
        # The activity says which half of the day.
        ("Dinner, back by 11", MORNING, datetime(2026, 10, 27, 23, 0, tzinfo=NY)),
        ("Party at Jess's, back around 1", EVENING, datetime(2026, 10, 28, 1, 0, tzinfo=NY)),
        ("Brunch at Sarabeth's, back by 1", MORNING, datetime(2026, 10, 27, 13, 0, tzinfo=NY)),
        ("Concert, back by 12", EVENING, datetime(2026, 10, 28, 0, 0, tzinfo=NY)),
        # Only one is likely: 9 AM tomorrow is 15 hours away.
        ("Walking to Sam's until 9", EVENING, datetime(2026, 10, 27, 21, 0, tzinfo=NY)),
        # Tomorrow: 9 PM tomorrow is more than 24 hours away.
        ("Grandma's tomorrow, back by 9", EVENING, datetime(2026, 10, 28, 9, 0, tzinfo=NY)),
    ],
)
def test_am_or_pm_from_the_plan(text, now, expected):
    plan = read(text, now)
    assert plan.return_by == expected and plan.choices == []


@pytest.mark.parametrize(
    ("text", "minutes"),
    [
        ("Dinner, home ~quarter to 11", 280),
        ("Study at the library until half past 9", 205),
        ("Date night, home by 10ish", 235),
        ("Out with friends for a couple of hours", 120),
        ("Shopping for a few hours", 180),
        ("Going to Brooklyn for 2-3 hours", 180),
        ("At Mike's, back in an hour or two", 120),
        ("Walking home from the bar, 20 min", 20),
        ("Movie for two hours", 120),
    ],
)
def test_time_phrases(text, minutes):
    assert read(text).return_by == EVENING + timedelta(minutes=minutes)


def test_dot_in_a_time():
    # "11.30" is 11:30, not 11; "1.5 hours" is still a length.
    plan = read("showup at store and be back by 11.30", MORNING)
    assert plan.destination == "store"
    assert plan.choices == [
        datetime(2026, 10, 27, 11, 30, tzinfo=NY),
        datetime(2026, 10, 27, 23, 30, tzinfo=NY),
    ]
    assert read("Gym for 1.5 hours").return_by == EVENING + timedelta(minutes=90)
    assert read("Dinner, home by 10.15").return_by == datetime(2026, 10, 27, 22, 15, tzinfo=NY)


def test_am_isnt_a_minute():
    # "a m" in "2:30 am" used to be read as "a minute".
    assert read("Late shift at work, back at 2:30 am").return_by == datetime(
        2026, 10, 28, 2, 30, tzinfo=NY
    )


def test_not_a_real_time():
    plan = read("Back by 9:75")
    assert plan.return_by is None and plan.problem


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("Dinner at Olive Garden on Main St", "Olive Garden on Main St"),
        ("Coffee with Priya at Blue Bottle", "Blue Bottle"),
        ("Bar crawl downtown, home", "Bar crawl downtown"),
        ("Olive Garden, back by 11", "Olive Garden"),
        ("The Home Depot", "The Home Depot"),
        ("to the gym.", "the gym"),
        ("", None),
        (None, None),
    ],
)
def test_clean_place(given, expected):
    assert plans._clean_place(given) == expected


def test_claude_unclear_am_pm_is_asked(monkeypatch):
    def fake_claude(text, now):
        fields = {
            "destination": "Blue Bottle",
            "back_by_time": "11:00",
            "am_pm_unclear": True,
            "day": "today",
            "minutes_from_now": None,
        }
        fields["other_time"] = plans._other_half(fields["back_by_time"])
        return fields

    monkeypatch.setattr(plans, "ask_claude", fake_claude)
    plan = read("Coffee at Blue Bottle, back by 11", MORNING)
    assert plan.source == "ai"
    assert len(plan.choices) == 2


def test_the_case_list_never_errs_early_with_the_basic_reader(monkeypatch):
    """evals/plan_cases.py: the built-in reader must never give a too-early or made-up time."""
    from evals.plan_cases import CASES
    from evals.scoring import DANGEROUS, grade_time, read_case

    monkeypatch.setattr(get_settings(), "ai_provider", "none")
    grades = []
    for now_text, text, _, expected in CASES:
        now, plan = read_case(now_text, text)
        grades.append(grade_time(plan, now, expected))
    assert "crashed" not in grades
    assert not DANGEROUS & set(grades)
    assert grades.count("right") >= len(CASES) - 2


def test_plan_endpoint_needs_login(client):
    r = client.post("/v1/check-ins/plan", json={"text": "x", "now": EVENING.isoformat()})
    assert r.status_code == 401
