"""
Score how well a reader fills in Start Session from plans typed in plain
words, using the cases in evals/plan_cases.py.

    python scripts/score_plans.py --reader basic
    python scripts/score_plans.py --reader ollama [--model llama3.2]
    python scripts/score_plans.py --reader claude      (needs ANTHROPIC_API_KEY)

A time earlier than the person meant is the dangerous mistake: it alerts
their Circle while they're still out. A later time, or asking for the time,
is a safe miss.
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import plans  # noqa: E402
from app.config import get_settings  # noqa: E402
from evals.plan_cases import CASES  # noqa: E402
from evals.scoring import DANGEROUS, DAY, grade_time, read_case, same_place  # noqa: E402


def show(plan: plans.Plan | None) -> str:
    def clock(when: datetime) -> str:
        day = "tomorrow " if when.date() > DAY.date() else ""
        return day + when.strftime("%I:%M %p").lstrip("0")

    if plan is None:
        return "CRASHED"
    if plan.choices:
        return "asks " + " or ".join(clock(c) for c in plan.choices)
    return clock(plan.return_by) if plan.return_by else f"no time ({plan.problem})"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--reader", choices=["basic", "ollama", "claude"], default="basic")
    parser.add_argument("--model", help="Ollama or Claude model to use instead of the setting")
    args = parser.parse_args()

    settings = get_settings()
    settings.ai_provider = "none" if args.reader == "basic" else args.reader
    if args.model and args.reader == "ollama":
        settings.ollama_model = args.model
    elif args.model:
        settings.ai_model = args.model

    grades: dict[str, int] = {}
    places_right = 0
    sources: dict[str, int] = {}
    misses: list[str] = []
    started = time.time()
    for now_text, text, place, expected in CASES:
        now, plan = read_case(now_text, text)
        grade = grade_time(plan, now, expected)
        grades[grade] = grades.get(grade, 0) + 1
        source = plan.source if plan else "crashed"
        sources[source] = sources.get(source, 0) + 1
        place_ok = plan is not None and same_place(plan.destination, place)
        places_right += place_ok
        if grade != "right" or not place_ok:
            want = expected if not isinstance(expected, tuple) else " or ".join(expected)
            misses.append(
                f"  [{grade:7}] {now_text} {text!r}\n"
                f"            got: {plan.destination if plan else None!r}, {show(plan)}\n"
                f"           want: {place!r}, {want if want is not None else 'no time'}"
            )

    total = len(CASES)
    took = time.time() - started
    print(f"Reader: {args.reader}" + (f" ({args.model})" if args.model else ""))
    print("\n".join(misses) or "  (no misses)")
    print()
    print(f"Time right:   {grades.get('right', 0)}/{total}")
    print(f"Safe misses:  {grades.get('asked', 0) + grades.get('late', 0)} (asked or later)")
    print(f"DANGEROUS:    {sum(grades.get(g, 0) for g in DANGEROUS)} (too early or made up)")
    print(f"Crashed:      {grades.get('crashed', 0)}")
    print(f"Place right:  {places_right}/{total}")
    print(f"Read by:      {sources}")
    print(f"Speed:        {took / total:.1f} s per plan")


if __name__ == "__main__":
    main()
