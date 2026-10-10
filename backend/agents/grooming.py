"""Grooming Agent: brushing, teeth, nails, ear and skin checks, plus bath guidance."""
import time
from datetime import date, timedelta

from agents.common import ai_tip
from state import PetCareState, make_trace
from tools.care_schedule import build_grooming


def grooming_node(state: PetCareState):
    t = time.time()
    a = state["assessment"]
    c = state.get("constraints") or {}
    profile = state.get("profile") or {}

    interval = c.get("grooming_interval_weeks")
    result = build_grooming(a["brushing_per_week"], a["species"], a["bath"], list(a["grooming_notes"]), interval)
    result["ai_tip"] = ai_tip(profile, "grooming routine", f"brushing {a['brushing_per_week']} times a week")

    reminders = []
    if interval:
        due = (date.today() + timedelta(weeks=interval)).isoformat()
        reminders.append({
            "title": f"Grooming session for {profile.get('name') or 'your pet'}", "due_date": due, "category": "grooming", "repeat_weeks": interval,
        })
    summary = f"Brushing {a['brushing_per_week']}x/week, weekly nail and ear/skin checks"
    if interval:
        summary += f", grooming every {interval} weeks"
    return {
        "results": {"grooming": {**result, "reminders_to_create": reminders}},
        "completed_agents": ["grooming"],
        "trace": [make_trace("Grooming Agent", summary, t)],
    }
