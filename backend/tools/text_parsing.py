"""Small regex-based extractors shared by the profile and follow-up agents.

They run before (or instead of) the language model so that behaviour stays
predictable even with a 3B model.
"""
import re
from typing import Any, Dict, List

from tools.reminders import parse_date, parse_interval_weeks

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

_DAY_PATTERNS = {
    "Monday": r"mon(?:day)?s?",
    "Tuesday": r"tue(?:s(?:day)?)?s?",
    "Wednesday": r"wed(?:nesday)?s?",
    "Thursday": r"thu(?:rs)?(?:day)?s?",
    "Friday": r"fri(?:day)?s?",
    "Saturday": r"saturdays?",
    "Sunday": r"sundays?",
}

AWAY_RE = re.compile(
    r"\b(won'?t be|will not be|can'?t|cannot|not (?:at )?home|away|busy|out of town|out all day|"
    r"skip|no walk|off|travell?ing|working late)\b",
    re.I,
)

SPECIES_WORDS = {
    "dog": "dog", "puppy": "dog", "pup": "dog",
    "cat": "cat", "kitten": "cat",
    "rabbit": "rabbit", "bunny": "rabbit",
    "hamster": "hamster", "guinea pig": "guinea pig",
    "parrot": "bird", "bird": "bird",
}

BREEDS = [
    "golden retriever", "labrador", "german shepherd", "beagle", "pug", "french bulldog", "bulldog",
    "poodle", "husky", "border collie", "shih tzu", "boxer", "rottweiler", "dachshund", "pomeranian",
    "indian pariah", "indie", "rajapalayam", "doberman", "corgi", "spaniel", "persian", "siamese",
    "maine coon", "bengal", "ragdoll", "british shorthair",
]


def extract_days(text: str) -> List[str]:
    found = set()
    low = text.lower()
    for day, pat in _DAY_PATTERNS.items():
        if re.search(rf"\b{pat}\b", low):
            found.add(day)
    if re.search(r"\bweekends?\b", low):
        found.update(["Saturday", "Sunday"])
    if re.search(r"\bweekdays?\b", low):
        found.update(DAYS[:5])
    return [d for d in DAYS if d in found]


def extract_pet_fields(text: str) -> Dict[str, Any]:
    """Pull name, species, breed, age (years) and weight (kg) out of free text."""
    out: Dict[str, Any] = {}
    low = text.lower()

    m = re.search(r"\b(?:named|called|name is|name's)\s+([A-Za-z]+)", text)
    if m:
        out["name"] = m.group(1).capitalize()

    for word in sorted(SPECIES_WORDS, key=len, reverse=True):
        if re.search(rf"\b{word}s?\b", low):
            out["species"] = SPECIES_WORDS[word]
            break

    for breed in BREEDS:
        if breed in low:
            out["breed"] = breed.title()
            break

    m = re.search(r"(\d+(?:\.\d+)?)\s*[- ]?(?:years?|yrs?|y)[- ]?(?:old)?\b", low)
    if m:
        out["age"] = float(m.group(1))
    else:
        m = re.search(r"(\d+)\s*[- ]?months?[- ]?(?:old)?\b", low)
        if m:
            out["age"] = round(int(m.group(1)) / 12, 2)

    m = re.search(r"(\d+(?:\.\d+)?)\s*(kgs?|kilos?|lbs?|pounds?)\b", low)
    if m:
        val = float(m.group(1))
        out["weight_kg"] = round(val * 0.4536, 1) if m.group(2).startswith(("lb", "pound")) else val

    m = re.search(r"\b(low|moderate|high)[- ](?:activity|energy)\b", low)
    if m:
        out["activity_level"] = m.group(1)
    return out


def extract_constraints(text: str) -> Dict[str, Any]:
    """Scheduling hints: away days, time-of-day preference, appointments, grooming interval."""
    low = text.lower()
    days = extract_days(text)
    constraints: Dict[str, Any] = {
        "unavailable_days": days if (days and AWAY_RE.search(text)) else [],
        "time_pref": "",
        "appointments": [],
        "grooming_interval_weeks": None,
    }

    morning = re.search(r"\bmornings?\b|before work", low)
    evening = re.search(r"\bevenings?\b|after work", low)
    if morning and not evening:
        constraints["time_pref"] = "morning"
    elif evening and not morning:
        constraints["time_pref"] = "evening"

    when = parse_date(text)
    if when:
        vet_words = re.search(r"\bvet\b|veterinar|check-?up", low)
        if re.search(r"vaccin|booster|\bshots?\b", low):
            constraints["appointments"].append({"title": "Vaccination", "date": when.isoformat()})
        elif vet_words:
            constraints["appointments"].append({"title": "Vet appointment", "date": when.isoformat()})
        elif re.search(r"groom", low):
            constraints["appointments"].append({"title": "Grooming appointment", "date": when.isoformat()})
        elif re.search(r"appointment", low):
            constraints["appointments"].append({"title": "Appointment", "date": when.isoformat()})

    if re.search(r"groom|bath|haircut", low):
        constraints["grooming_interval_weeks"] = parse_interval_weeks(text)
    return constraints
