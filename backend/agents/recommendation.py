"""Care Plan Agent: merges specialist results into one plan and writes the reply."""
import time
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List

from agents.appointment import VET_PREP
from config import DISCLAIMER
from state import PetCareState, make_trace
from tools.care_schedule import build_calendar

PLAN_KEYS = ("exercise", "grooming", "feeding", "appointment")


def _merge_plan(state: PetCareState) -> Dict[str, Any]:
    results = state.get("results") or {}
    plan: Dict[str, Any] = deepcopy(state.get("previous_plan") or {})
    for key in ("exercise", "grooming", "feeding"):
        if key in results:
            plan[key] = {k: v for k, v in results[key].items() if k != "reminders_to_create"}
    if "appointment" in results:
        existing: List[Dict[str, Any]] = plan.get("appointments", [])
        for a in results["appointment"]["appointments"]:
            if not any(e["title"] == a["title"] and e["date"] == a["date"] for e in existing):
                existing.append(a)
        plan["appointments"] = sorted(existing, key=lambda x: x["date"])
    profile = state.get("profile") or {}
    plan.update({
        "pet_name": profile.get("name") or "your pet",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "revision": plan.get("revision", 0) + 1 if state.get("previous_plan") else 1,
        "assessment": {k: state["assessment"][k] for k in ("stage", "size", "activity_level", "attention_points")},
        "disclaimer": DISCLAIMER,
    })
    plan["week"] = build_calendar(plan)
    return plan


def _reply(state: PetCareState) -> str:
    results = state["results"]
    name = (state.get("profile") or {}).get("name") or "your pet"
    intent = state["intent"]
    attention = (state.get("assessment") or {}).get("attention_points", [])
    heading = {
        "care_plan": f"Here's {name}'s weekly care plan.",
        "exercise": f"I've updated {name}'s exercise schedule.",
        "grooming": f"I've updated {name}'s grooming schedule.",
        "feeding": f"I've updated {name}'s feeding schedule.",
        "vet_appointment": f"Here's how I can help with {name}'s appointments.",
        "vaccination_reminder": f"Here's how I can help with {name}'s vaccinations.",
    }.get(intent, f"I've updated {name}'s care plan.")
    lines = [heading]

    ex = results.get("exercise")
    if ex:
        lines.append(f"- **Exercise:** about {ex['daily_minutes']} minutes a day, with a longer outing at the weekend.")
        if ex["unavailable_days"]:
            lines.append(f"- **Away days:** {', '.join(ex['unavailable_days'])}. I've spread part of the missed exercise across nearby days.")
    gr = results.get("grooming")
    if gr:
        days = ", ".join(d[:3] for d in gr["brushing"]["days"]) or "as needed"
        lines.append(f"- **Grooming:** brushing {gr['brushing']['per_week']}x a week ({days}), plus a weekly nail, ear, and skin check.")
    fe = results.get("feeding")
    if fe:
        lines.append(f"- **Feeding:** {fe['meals_per_day']} meals a day at {', '.join(fe['times'])}. Ask your vet about portion sizes.")

    ap = results.get("appointment")
    if ap:
        for a in ap["appointments"]:
            lines.append(f"- **{a['title']}:** {a['date']}. I saved a reminder.")
        if any(r["repeat_weeks"] for r in ap["reminders_to_create"]):
            lines.append("- **Repeating reminder:** saved for your grooming schedule.")
        lines.extend(f"- {n}" for n in ap["notes"])
        if ap["needs_date"]:
            lines.append("- Tell me the date and I'll set a reminder, for example: \"Next vet appointment 20 October\".")
        if intent in ("vet_appointment", "vaccination_reminder"):
            lines.append("\nBefore the visit:")
            lines.extend(f"- {p}" for p in VET_PREP)

    if intent == "care_plan":
        lines.extend(f"- **Keep in mind:** {point}" for point in attention)
    lines.append("\n" + DISCLAIMER)
    return "\n".join(lines)


def recommendation_node(state: PetCareState):
    t = time.time()
    results = state.get("results") or {}

    if not (state.get("assessment") or {}).get("ready") and state.get("intent") not in ("general_question", "urgent_health", "pet_profile"):
        reply = ("I need a few details about your pet before I can plan. Add a profile on the My pets page, "
                 "or tell me the species, age, and weight.")
        return {"care_plan": None, "reply": reply, "trace": [make_trace("Care Plan Agent", "Waiting for pet details", t)]}

    appt = results.get("appointment")
    changes_plan = any(k in results for k in ("exercise", "grooming", "feeding")) or bool(appt and appt["appointments"])

    if not changes_plan and not appt:
        # General answer or urgent referral: keep the reply the General Care Agent wrote.
        reply = state.get("reply") or ""
        return {"care_plan": None, "reply": reply, "trace": [make_trace("Care Plan Agent", "Reply prepared (no plan changes)", t)]}

    reply = _reply(state)
    if not changes_plan:
        return {"care_plan": None, "reply": reply, "trace": [make_trace("Care Plan Agent", "Reply prepared (no plan changes)", t)]}

    plan = _merge_plan(state)
    parts = [k for k in PLAN_KEYS if k in results]
    return {
        "care_plan": plan,
        "reply": reply,
        "trace": [make_trace("Care Plan Agent", f"Plan revision {plan['revision']} built from: {', '.join(parts)}", t)],
    }
