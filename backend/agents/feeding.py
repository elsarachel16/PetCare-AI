"""Feeding Agent: organises meal times. It never sets portion sizes or medical diets."""
import time

from agents.common import ai_tip
from state import PetCareState, make_trace
from tools.care_schedule import build_feeding


def feeding_node(state: PetCareState):
    t = time.time()
    a = state["assessment"]
    profile = state.get("profile") or {}

    result = build_feeding(a["meals_per_day"])
    result["notes"] = list(a["feeding_notes"])
    result["ai_tip"] = ai_tip(profile, "feeding schedule", f"{a['meals_per_day']} meals a day, life stage {a['stage']}")

    return {
        "results": {"feeding": result},
        "completed_agents": ["feeding"],
        "trace": [make_trace("Feeding Agent", f"{result['meals_per_day']} meals/day at {', '.join(result['times'])}; portions left to the vet", t)],
    }
