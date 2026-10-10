"""Exercise Agent: builds a weekly activity schedule."""
import time

from agents.common import ai_tip
from state import PetCareState, make_trace
from tools.care_schedule import build_weekly_exercise


def exercise_node(state: PetCareState):
    t = time.time()
    a = state["assessment"]
    c = state.get("constraints") or {}
    profile = state.get("profile") or {}

    away = c.get("unavailable_days") or []
    week, changes = build_weekly_exercise(a["exercise_minutes"], a["species"], away, c.get("time_pref", ""))
    tip = ai_tip(profile, "daily exercise routine", f"about {a['exercise_minutes']} minutes a day, life stage {a['stage']}")

    result = {
        "daily_minutes": a["exercise_minutes"],
        "week": week,
        "notes": list(a["exercise_notes"]),
        "unavailable_days": away,
        "ai_tip": tip,
    }
    summary = f"Built weekly schedule, about {a['exercise_minutes']} min/day"
    if away:
        summary += f", away on {', '.join(away)}"
    return {
        "results": {"exercise": result},
        "completed_agents": ["exercise"],
        "trace": [make_trace("Exercise Agent", summary, t, adjustments=changes)],
    }
