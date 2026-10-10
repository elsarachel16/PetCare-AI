"""Custom @tool functions for the follow-up agent.

Same pattern as your Trip Concierge tools.py: plain Python functions with input
cleaning, decorated with @tool so a ReAct agent can call them.

    cost_calculator   ->  care_calculator
    destination_info  ->  pet_care_info
    (new)                 current_care_plan   reads the plan being discussed
"""
import re
from contextvars import ContextVar
from datetime import date, timedelta

from langchain_core.tools import tool

from tools.reminders import parse_date

# The follow-up agent sets this before each call so the plan tool knows which plan is being discussed.
CURRENT_PLAN_SUMMARY: ContextVar[str] = ContextVar("current_plan_summary", default="")

_SPECIES_INFO = {
    "dog": "Puppy under 1 year, adult 1 to 7, senior from about 7. Most adult dogs benefit from daily walks, "
           "regular brushing, and a vet check-up at least once a year.",
    "cat": "Kitten under 1 year, adult 1 to 10, senior from about 10. Cats need daily play, a clean litter tray, "
           "and a vet check-up at least once a year.",
    "rabbit": "Junior under 1 year, adult 1 to 6, senior from about 6. Rabbits need unlimited hay, several hours "
              "of free-roam time a day, and regular vet check-ups.",
}


def _clean_number(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).strip().replace(",", "").replace("%", ""))


@tool
def care_calculator(expression: str) -> str:
    """Do pet-care math: weekly totals, kg/lb conversion, or the next date for a repeating task.
    Accepts inputs like '30 min * 5 days', '24 kg to lb', '10 lb to kg',
    or 'every 4 weeks from 2026-10-01'. Pass the operation as plain text."""
    text = expression.lower().strip()

    m = re.search(r"every\s+(\d+)\s*weeks?\s+from\s+(.+)", text)
    if m:
        start = parse_date(m.group(2))
        if start:
            weeks = int(m.group(1))
            nxt = start + timedelta(weeks=weeks)
            while nxt <= date.today():
                nxt += timedelta(weeks=weeks)
            return f"Every {weeks} weeks from {start.isoformat()}: next on {nxt.isoformat()}"

    m = re.search(r"([\d.,]+)\s*(kg|kgs|lb|lbs)\s*(?:to|in|into)\s*(kg|kgs|lb|lbs)", text)
    if m:
        amount = _clean_number(m.group(1))
        src_kg = m.group(2).startswith("kg")
        dst_kg = m.group(3).startswith("kg")
        if src_kg == dst_kg:
            return f"{amount:g} {m.group(2)} is already in {m.group(3)}"
        return f"{amount:g} kg = {amount * 2.2046:.1f} lb" if src_kg else f"{amount:g} lb = {amount * 0.4536:.1f} kg"

    m = re.search(r"([\d.,]+)\s*(?:min|minutes)?\s*[*x]\s*([\d.,]+)", text)
    if m:
        a, b = _clean_number(m.group(1)), _clean_number(m.group(2))
        total = a * b
        return f"{a:g} x {b:g} = {total:g} (about {total / 60:.1f} hours if these are minutes)"

    return "Couldn't parse that. Try '30 min * 5 days', '24 kg to lb', or 'every 4 weeks from 2026-10-01'."


@tool
def pet_care_info(species: str) -> str:
    """Look up general life-stage ages and care basics for a species (dog, cat or rabbit).
    This is general guidance, not veterinary advice."""
    info = _SPECIES_INFO.get(species.strip().lower())
    if not info:
        return f"No cached info for '{species}'. Known species: {', '.join(_SPECIES_INFO)}. Ask a vet for other species."
    return f"{species.title()}: {info}"


@tool
def current_care_plan(question_topic: str = "") -> str:
    """Return a short summary of the pet's current care plan (exercise, grooming, feeding, appointments).
    Call this before answering questions about the plan. The argument can be left empty."""
    return CURRENT_PLAN_SUMMARY.get() or "There is no care plan yet for this pet."


ALL_TOOLS = [care_calculator, pet_care_info, current_care_plan]
