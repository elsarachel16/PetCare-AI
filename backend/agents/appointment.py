"""Appointment & Reminder Agent: turns dates and intervals in the message into appointments and reminders."""
import time
from datetime import date, timedelta

from state import PetCareState, make_trace

VET_PREP = [
    "Bring vaccination records and any previous medical notes.",
    "Write down questions, plus any changes in appetite, energy, drinking, or weight.",
    "List current food, treats, supplements, and any medication.",
    "Bring a stool sample if your vet has asked for one.",
    "Bring a leash or carrier, and a favourite treat to keep things calm.",
    "Arrive a few minutes early so your pet can settle.",
]


def appointment_node(state: PetCareState):
    t = time.time()
    c = state.get("constraints") or {}
    profile = state.get("profile") or {}
    name = profile.get("name") or "your pet"
    intent = state.get("intent")

    appointments, reminders = [], []
    for a in c.get("appointments", []):
        appointments.append({"title": a["title"], "date": a["date"]})
        reminders.append({"title": f"{a['title']} for {name}", "due_date": a["date"], "category": "health", "repeat_weeks": None})
        prep_day = date.fromisoformat(a["date"]) - timedelta(days=1)
        if prep_day >= date.today():
            reminders.append({
                "title": f"Prepare for {name}'s {a['title'].lower()} tomorrow",
                "due_date": prep_day.isoformat(), "category": "health", "repeat_weeks": None,
            })

    interval = c.get("grooming_interval_weeks")
    if interval:
        reminders.append({
            "title": f"Grooming session for {name}",
            "due_date": (date.today() + timedelta(weeks=interval)).isoformat(),
            "category": "grooming", "repeat_weeks": interval,
        })

    notes = []
    if intent == "vaccination_reminder":
        notes.append("Vaccination and parasite-prevention schedules depend on age, location, and lifestyle. "
                     "Your vet sets the schedule; I can remind you once you have a date.")
    needs_date = not appointments and intent in ("vet_appointment", "vaccination_reminder") and not interval

    summary = f"{len(appointments)} appointment(s), {len(reminders)} reminder(s) prepared"
    return {
        "results": {"appointment": {
            "appointments": appointments, "reminders_to_create": reminders, "vet_prep": VET_PREP,
            "notes": notes, "needs_date": needs_date,
        }},
        "completed_agents": ["appointment"],
        "trace": [make_trace("Appointment & Reminder Agent", summary, t)],
    }
