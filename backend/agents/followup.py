"""Follow-up Pet Assistant: edits the existing plan from a natural-language request (rule-based, so it is
reliable with a small model), or answers questions about it with the ReAct agent."""
import re
import time
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List

from agents.followup_agent import answer_question
from state import PetCareState, make_trace
from tools.care_schedule import DAYS, apply_unavailable, build_calendar, build_weekly_exercise, brush_days
from tools.pet_calculator import round5
from tools.text_parsing import AWAY_RE, extract_days

HELP = (
    "I couldn't tell what to change. You can say things like:\n"
    "- \"I won't be home on Wednesday\"\n"
    "- \"Make the walks 20 minutes longer\" or \"Make walks 40 minutes\"\n"
    "- \"Move grooming to Saturday\""
)


def _plan_summary(plan: Dict[str, Any]) -> str:
    bits = []
    ex = plan.get("exercise")
    if ex:
        bits.append(f"exercise about {ex['daily_minutes']} min/day, away days: {', '.join(ex.get('unavailable_days') or []) or 'none'}")
    gr = plan.get("grooming")
    if gr:
        bits.append(f"brushing {gr['brushing']['per_week']}x/week on {', '.join(gr['brushing']['days'])}")
    fe = plan.get("feeding")
    if fe:
        bits.append(f"{fe['meals_per_day']} meals/day at {', '.join(fe['times'])}")
    if plan.get("appointments"):
        bits.append("appointments: " + "; ".join(f"{a['title']} on {a['date']}" for a in plan["appointments"]))
    return "; ".join(bits)


def _rebuild_exercise(plan: Dict[str, Any], minutes: int, species: str) -> List[str]:
    ex = plan["exercise"]
    away = ex.get("unavailable_days") or []
    week, changes = build_weekly_exercise(minutes, species, away)
    ex["daily_minutes"], ex["week"] = minutes, week
    return changes


def followup_node(state: PetCareState):
    t = time.time()
    plan: Dict[str, Any] = deepcopy(state["previous_plan"])
    msg = state.get("user_message", "")
    low = msg.lower()
    pet = state.get("pet") or {}
    species = (pet.get("species") or "dog").lower()
    days = extract_days(msg)
    changes: List[str] = []
    answer = None
    ex = plan.get("exercise")

    if days and AWAY_RE.search(msg) and ex:
        ex["week"], changes = apply_unavailable(ex["week"], days, species)
        ex["unavailable_days"] = sorted(set(ex.get("unavailable_days") or []) | set(days), key=DAYS.index)
    elif ex and re.search(r"\b(walk|walks|exercise|play|activity)\b", low) and re.search(r"(\d+)\s*(?:min|minutes)", low):
        n = int(re.search(r"(\d+)\s*(?:min|minutes)", low).group(1))
        base = ex["daily_minutes"]
        if re.search(r"\b(longer|extra|more|increase)\b", low):
            target = base + n
        elif re.search(r"\b(shorter|less|reduce|fewer)\b", low):
            target = base - n
        else:
            target = n
        target = max(10, min(240, round5(target)))
        changes = [f"Daily exercise target changed from {base} to {target} min"] + _rebuild_exercise(plan, target, species)
    elif ex and re.search(r"\b(longer|shorter|reduce|increase)\b", low) and re.search(r"walk|exercise|play", low):
        factor = 1.2 if re.search(r"longer|increase", low) else 0.8
        base = ex["daily_minutes"]
        target = max(10, round5(base * factor))
        changes = [f"Daily exercise target changed from {base} to {target} min"] + _rebuild_exercise(plan, target, species)
    elif plan.get("grooming") and days and re.search(r"groom|brush", low) and re.search(r"move|change|switch|swap|instead|reschedule", low):
        g = plan["grooming"]
        n = g["brushing"]["per_week"]
        merged = list(days) + [d for d in brush_days(n) if d not in days]
        g["brushing"]["days"] = sorted(merged[:n] if n else [], key=DAYS.index)
        changes = [f"Brushing days are now {', '.join(g['brushing']['days'])}"]
    else:
        # Questions go to the tool-using ReAct agent (with per-pet memory), as in the Trip Concierge.
        thread = f"pet-{state.get('pet_id') or 'guest'}"
        answer = answer_question(thread, msg, _plan_summary(plan))

    if changes:
        plan["week"] = build_calendar(plan)
        plan["generated_at"] = datetime.now().isoformat(timespec="seconds")
        plan["revision"] = plan.get("revision", 1) + 1
        reply = "Done. Here's what changed:\n" + "\n".join(f"- {c}" for c in changes)
        trace_msg = f"Applied {len(changes)} change(s); plan revision {plan['revision']}"
        new_plan = plan
    elif answer:
        reply, trace_msg, new_plan = answer, "Answered from the current plan", None
    else:
        summary = _plan_summary(plan)
        reply = HELP + (f"\n\nCurrent plan: {summary}." if summary else "")
        trace_msg, new_plan = "No change recognised; asked for clarification", None

    return {
        "care_plan": new_plan,
        "plan_changes": changes,
        "reply": reply,
        "results": {},
        "trace": [make_trace("Follow-up Pet Assistant", trace_msg, t, changes=changes)],
    }
