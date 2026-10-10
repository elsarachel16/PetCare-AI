"""Rule-based care calculations.

These are general, widely used care guidelines for planning a routine. They are
NOT veterinary advice and never set food quantities or medical treatment.
"""
from typing import Any, Dict, List, Optional

HIGH_ENERGY = (
    "labrador", "golden retriever", "border collie", "husky", "german shepherd", "australian shepherd",
    "jack russell", "vizsla", "weimaraner", "malinois", "pointer", "spaniel", "retriever",
)
SHORT_NOSED = (
    "pug", "bulldog", "french bulldog", "boston terrier", "boxer", "shih tzu", "pekingese",
    "persian", "exotic shorthair",
)
LONG_COAT = (
    "golden retriever", "husky", "collie", "shih tzu", "pomeranian", "samoyed", "persian",
    "maine coon", "ragdoll", "afghan", "lhasa", "poodle", "spitz",
)
DOUBLE_COAT = ("labrador", "retriever", "german shepherd", "husky", "corgi", "samoyed", "akita")


def _match(breed: str, names) -> bool:
    return any(n in breed for n in names)


def round5(x: float) -> int:
    return max(5, int(5 * round(x / 5)))


def life_stage(species: str, age: Optional[float]) -> str:
    if age is None:
        return "adult"
    young_cut, senior_cut = {"dog": (1, 7), "cat": (1, 10), "rabbit": (1, 6)}.get(species, (1, 5))
    if age < young_cut:
        return {"dog": "puppy", "cat": "kitten"}.get(species, "young")
    if age >= senior_cut:
        return "senior"
    return "adult"


def size_class(species: str, weight_kg: Optional[float]) -> Optional[str]:
    if species != "dog" or not weight_kg:
        return None
    if weight_kg < 10:
        return "small"
    if weight_kg < 25:
        return "medium"
    if weight_kg < 40:
        return "large"
    return "giant"


def exercise_target(species: str, stage: str, level: str, breed: str, size: Optional[str]):
    """Return (minutes per day, notes)."""
    notes: List[str] = []
    if species == "dog":
        base = {"low": 30, "moderate": 45, "high": 70}[level]
        if stage == "adult" and _match(breed, HIGH_ENERGY):
            base += 10
            notes.append(f"{breed.title()} dogs are usually high-energy, so the daily target is a little higher.")
        if size == "small":
            base *= 0.85
        elif size == "giant":
            base *= 0.9
        if stage == "puppy":
            base = min(base, 30)
            notes.append("Puppies do best with several short, gentle sessions. Ask your vet how much exercise suits their growth stage.")
        elif stage == "senior":
            base *= 0.7
            notes.append("Senior dogs usually prefer shorter, gentler walks. Watch for stiffness and mention it to your vet.")
        if _match(breed, SHORT_NOSED):
            base = min(base, 30)
            notes.append("Short-nosed breeds overheat easily. Walk in the cooler parts of the day and avoid hard exercise in heat.")
        notes.append("Walks are split into morning and evening sessions when the total is long.")
    elif species == "cat":
        base = {"low": 15, "moderate": 25, "high": 40}[level]
        if stage == "kitten":
            base += 10
        elif stage == "senior":
            base *= 0.7
        notes.append("Cats prefer short bursts of play. Split the session if your cat loses interest quickly.")
    elif species == "rabbit":
        base = {"low": 120, "moderate": 180, "high": 240}[level]
        notes.append("Rabbits need several hours of supervised time outside their enclosure each day.")
    else:
        base = {"low": 20, "moderate": 40, "high": 60}[level]
        notes.append("Time outside the cage or enclosure is a general guide. Ask your vet about your species.")
    return round5(base), notes


def meals_per_day(species: str, stage: str) -> int:
    if species == "dog":
        return 3 if stage == "puppy" else 2
    if species == "cat":
        return 3 if stage == "kitten" else 2
    return 2


def feeding_notes(species: str, stage: str) -> List[str]:
    notes = [
        "This plan sets meal times only. Measure portions using the food label and your vet's advice.",
        "Keep fresh water available at all times.",
        "Change foods gradually over about a week to avoid stomach upset.",
    ]
    if stage in ("puppy", "kitten", "young"):
        notes.insert(1, "Young pets usually eat smaller meals more often. Ask your vet how to adjust as they grow.")
    if stage == "senior":
        notes.insert(1, "Senior pets may need diet changes. Ask your vet at the next check-up.")
    if species == "rabbit":
        notes.insert(1, "Unlimited hay should make up most of a rabbit's diet. Ask your vet about pellets and fresh greens.")
    return notes


def grooming_profile(species: str, breed: str) -> Dict[str, Any]:
    """Brushing frequency, bath guidance and notes."""
    notes: List[str] = []
    if species == "dog":
        if _match(breed, LONG_COAT):
            per_week = 4
            notes.append("Long or thick coats tangle easily, so brushing is more frequent.")
        elif _match(breed, DOUBLE_COAT):
            per_week = 3
            notes.append("Double coats shed heavily. Brush more often during shedding seasons.")
        else:
            per_week = 2
        bath = {"interval_weeks": 8, "text": "Roughly every 6 to 8 weeks, or when visibly dirty. Ask your groomer or vet about a shampoo that suits your dog's skin."}
    elif species == "cat":
        per_week = 4 if _match(breed, LONG_COAT) else 1
        bath = {"interval_weeks": None, "text": "Most cats groom themselves. Bathe only if your vet or groomer suggests it."}
    elif species == "rabbit":
        per_week = 1
        bath = {"interval_weeks": None, "text": "Rabbits should not be bathed. Spot-clean only and ask your vet if fur stays soiled."}
        notes.append("Brush more often while your rabbit is moulting.")
    else:
        per_week = 0
        bath = {"interval_weeks": None, "text": "Ask your vet about bathing and coat care for this species."}
    notes.append("Check ears, skin, and nails once a week. Contact your vet if you notice redness, odour, lumps, or hair loss.")
    return {"brushing_per_week": per_week, "bath": bath, "notes": notes}


def assess(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Turn a pet profile into everything the specialist agents need."""
    species = (profile.get("species") or "").lower().strip()
    if not species:
        return {"ready": False, "missing": ["species"]}

    breed = (profile.get("breed") or "").lower()
    age = profile.get("age")
    weight = profile.get("weight_kg")
    level = (profile.get("activity_level") or "moderate").lower()
    if level not in ("low", "moderate", "high"):
        level = "moderate"

    stage = life_stage(species, age)
    size = size_class(species, weight)
    minutes, ex_notes = exercise_target(species, stage, level, breed, size)
    groom = grooming_profile(species, breed)

    attention: List[str] = []
    if stage in ("puppy", "kitten", "young"):
        attention.append("Young pet: plan short sessions and book vaccination and parasite-prevention visits with your vet.")
    if stage == "senior":
        attention.append("Senior pet: schedule regular vet check-ups and watch for changes in mobility, appetite, or energy.")
    if _match(breed, SHORT_NOSED):
        attention.append("Short-nosed breed: avoid heat and strenuous exercise.")

    return {
        "ready": True,
        "species": species,
        "stage": stage,
        "size": size,
        "activity_level": level,
        "exercise_minutes": minutes,
        "exercise_notes": ex_notes,
        "meals_per_day": meals_per_day(species, stage),
        "feeding_notes": feeding_notes(species, stage),
        "brushing_per_week": groom["brushing_per_week"],
        "bath": groom["bath"],
        "grooming_notes": groom["notes"],
        "attention_points": attention,
    }
