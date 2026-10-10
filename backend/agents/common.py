"""Helpers shared by the specialist agents."""
from typing import Any, Dict, Optional

from llm import llm_text

SAFETY_SYSTEM = (
    "You are PetCare AI, a careful pet-care organiser. You give general care and scheduling "
    "information only. You never diagnose, never prescribe medication, never state exact food "
    "quantities, and you tell owners to ask a veterinarian about any health concern. "
    "Reply in plain text with no lists and no markdown."
)


def pet_line(profile: Dict[str, Any]) -> str:
    parts = []
    if profile.get("name"):
        parts.append(profile["name"])
    desc = " ".join(str(x) for x in (profile.get("breed"), profile.get("species")) if x)
    if desc:
        parts.append(desc)
    if profile.get("age") is not None:
        parts.append(f"{profile['age']} years old")
    if profile.get("weight_kg"):
        parts.append(f"{profile['weight_kg']} kg")
    if profile.get("activity_level"):
        parts.append(f"{profile['activity_level']} activity")
    return ", ".join(parts) or "an unnamed pet"


def ai_tip(profile: Dict[str, Any], topic: str, facts: str) -> Optional[str]:
    """One or two friendly, practical sentences from the model. None if the model is unavailable."""
    text = llm_text(
        SAFETY_SYSTEM,
        f"Pet: {pet_line(profile)}.\nTopic: {topic}.\nPlan facts: {facts}\n"
        "Write at most two short sentences with one practical tip for the owner.",
    )
    if not text:
        return None
    return text[:400]
