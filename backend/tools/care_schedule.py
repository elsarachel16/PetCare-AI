"""Builds weekly schedules and merges everything into one calendar."""
import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from tools.pet_calculator import round5

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# (minutes multiplier, activity label, split into morning + evening when long)
_PATTERNS = {
    "dog": [
        (1.0, "Walk", True), (1.1, "Walk with sniffing time", True), (1.0, "Walk", True),
        (1.1, "Play session (fetch or tug)", False), (1.0, "Walk", True),
        (1.4, "Long outdoor activity", False), (0.8, "Easy walk", True),
    ],
    "cat": [
        (1.0, "Wand-toy play", False), (1.0, "Climbing and chase play", False), (1.0, "Wand-toy play", False),
        (1.0, "Puzzle-feeder session", False), (1.0, "Wand-toy play", False),
        (1.2, "Long play session", False), (0.8, "Gentle play", False),
    ],
    "rabbit": [(1.0, "Free-roam time", False)] * 7,
}
_DEFAULT_PATTERN = [(1.0, "Out-of-cage enrichment", False)] * 7


def make_sessions(total: int, activity: str, split: bool, species: str, pref: str) -> List[Dict[str, Any]]:
    base = activity[0].lower() + activity[1:]
    if split and total >= 40:
        first = round5(total * 0.55)
        return [
            {"time": "07:30", "minutes": first, "label": f"Morning {base}"},
            {"time": "18:30", "minutes": max(5, total - first), "label": f"Evening {base}"},
        ]
    time_ = "07:30" if pref == "morning" else ("09:00" if activity.startswith("Long") else "18:00")
    return [{"time": time_, "minutes": total, "label": activity}]


def build_weekly_exercise(minutes: int, species: str, unavailable_days: Optional[List[str]] = None,
                          pref: str = "") -> Tuple[Dict[str, Any], List[str]]:
    pattern = _PATTERNS.get(species, _DEFAULT_PATTERN)
    week: Dict[str, Any] = {}
    for i, day in enumerate(DAYS):
        mult, label, split = pattern[i]
        total = round5(minutes * mult)
        week[day] = {
            "minutes": total, "activity": label, "split": split, "away": False, "note": "",
            "sessions": make_sessions(total, label, split, species, pref),
        }
    changes: List[str] = []
    if unavailable_days:
        week, changes = apply_unavailable(week, unavailable_days, species, pref)
    return week, changes


def resplit(day: Dict[str, Any], total: int, species: str, pref: str) -> Dict[str, Any]:
    day = dict(day)
    day["minutes"] = total
    day["sessions"] = make_sessions(total, day["activity"], day.get("split", False), species, pref)
    return day


def apply_unavailable(week: Dict[str, Any], days: List[str], species: str, pref: str = "") -> Tuple[Dict[str, Any], List[str]]:
    """Mark days as away days and move part of the lost exercise to the next free days."""
    changes: List[str] = []
    lost: Dict[str, int] = {}
    for d in days:
        if d in week and not week[d].get("away"):
            lost[d] = week[d]["minutes"]
            week[d] = {
                "minutes": 15, "activity": "Away day", "split": False, "sessions": [], "away": True,
                "note": "You're away. Ask someone to cover, or leave puzzle toys and indoor play.",
            }
            changes.append(f"{d}: marked as an away day (ask someone to cover, or 15 min of indoor play)")

    for d, minutes in lost.items():
        extra = max(minutes - 15, 0)
        idx = DAYS.index(d)
        targets = []
        for i in range(1, 7):
            nd = DAYS[(idx + i) % 7]
            if not week[nd].get("away"):
                targets.append(nd)
            if len(targets) == 2:
                break
        share = min(round5(extra / 2), 15) if extra >= 10 and targets else 0
        for nd in targets if share else []:
            week[nd] = resplit(week[nd], week[nd]["minutes"] + share, species, pref)
            changes.append(f"{nd}: +{share} min to make up for {d}")
    return week, changes


_BRUSH_DAYS = {
    0: [], 1: ["Sunday"], 2: ["Tuesday", "Saturday"], 3: ["Monday", "Wednesday", "Friday"],
    4: ["Monday", "Wednesday", "Friday", "Sunday"],
    5: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    6: DAYS[:6], 7: list(DAYS),
}


def brush_days(n: int) -> List[str]:
    return _BRUSH_DAYS[max(0, min(7, n))]


def build_grooming(per_week: int, species: str, bath: Dict[str, Any], notes: List[str],
                   professional_weeks: Optional[int] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "brushing": {"per_week": per_week, "days": brush_days(per_week), "time": "19:30"},
        "nail_check": {"day": "Sunday", "time": "10:00"},
        "ear_skin_check": {"day": "Sunday", "time": "10:15"},
        "bath": bath,
        "notes": notes,
        "professional_interval_weeks": professional_weeks,
    }
    if species in ("dog", "cat"):
        out["teeth"] = {"per_week": 3, "days": ["Tuesday", "Thursday", "Saturday"], "time": "20:00"}
    return out


_MEAL_TIMES = {
    1: ["08:00"], 2: ["07:30", "18:30"], 3: ["07:30", "12:30", "18:30"], 4: ["07:30", "11:30", "15:30", "19:30"],
}


def build_feeding(meals: int) -> Dict[str, Any]:
    meals = max(1, min(4, meals))
    times = _MEAL_TIMES[meals]
    if meals == 1:
        labels = ["Meal"]
    else:
        labels = ["Breakfast"] + ["Midday meal"] * (meals - 2) + ["Dinner"]
    return {"meals_per_day": meals, "times": times, "labels": labels}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def build_calendar(plan: Dict[str, Any], today: Optional[date] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Merge exercise, grooming, feeding and appointments into {weekday: [tasks sorted by time]}."""
    today = today or date.today()
    week: Dict[str, List[Dict[str, Any]]] = {d: [] for d in DAYS}

    def add(day: str, time_: str, task: str, category: str):
        week[day].append({"id": f"{day}|{time_}|{category}|{_slug(task)}", "time": time_, "task": task, "category": category})

    for day, info in (plan.get("exercise") or {}).get("week", {}).items():
        if info.get("away"):
            add(day, "12:00", "Away day: arrange cover or indoor play (15 min)", "exercise")
            continue
        for s in info.get("sessions", []):
            add(day, s["time"], f"{s['label']} ({s['minutes']} min)", "exercise")

    g = plan.get("grooming")
    if g:
        for d in g["brushing"]["days"]:
            add(d, g["brushing"]["time"], "Brush coat", "grooming")
        if g.get("teeth"):
            for d in g["teeth"]["days"]:
                add(d, g["teeth"]["time"], "Brush teeth", "grooming")
        add(g["nail_check"]["day"], g["nail_check"]["time"], "Nail check", "grooming")
        add(g["ear_skin_check"]["day"], g["ear_skin_check"]["time"], "Ear and skin check", "grooming")

    f = plan.get("feeding")
    if f:
        for d in DAYS:
            for t, label in zip(f["times"], f["labels"]):
                add(d, t, label, "feeding")

    for a in plan.get("appointments", []) or []:
        try:
            when = date.fromisoformat(a["date"])
        except (KeyError, ValueError):
            continue
        if 0 <= (when - today).days < 7:
            add(DAYS[when.weekday()], a.get("time") or "10:00", a["title"], "health")

    for d in DAYS:
        week[d].sort(key=lambda t: t["time"])
    return week
