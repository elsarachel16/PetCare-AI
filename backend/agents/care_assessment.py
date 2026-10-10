"""Care Assessment Agent: works out life stage, size and care targets (replaces the old budget check)."""
import time

from state import PetCareState, make_trace
from tools.pet_calculator import assess


def care_assessment_node(state: PetCareState):
    t = time.time()
    a = assess(state.get("profile") or {})
    if not a["ready"]:
        summary = "Not enough pet details yet (species missing)"
    else:
        size = f", {a['size']} size" if a["size"] else ""
        summary = (
            f"{a['stage'].title()} {a['species']}{size}; exercise target {a['exercise_minutes']} min/day; "
            f"{a['meals_per_day']} meals/day"
        )
    return {"assessment": a, "trace": [make_trace("Care Assessment Agent", summary, t)]}
