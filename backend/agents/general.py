"""General Care Agent: profile summaries, general questions, and safe handling of health concerns."""
import time

from agents.common import SAFETY_SYSTEM, pet_line
from llm import llm_text
from state import PetCareState, make_trace

URGENT_REPLY = (
    "This sounds like it could need a vet's attention, and I can't diagnose or treat health problems.\n"
    "- Contact your vet now. If it's out of hours or looks severe, go to an emergency vet clinic.\n"
    "- Keep {name} calm and warm, and don't give any human medication.\n"
    "- Have details ready: when it started, what {name} ate recently, and any medication or supplements."
)

FALLBACK = (
    "I can organise care for {name}: a weekly care plan, exercise, grooming, feeding times, and "
    "vet or grooming reminders. For a specific health or diet question, your vet is the right person to ask.\n"
    "Try: \"Create a weekly care plan for {name}\"."
)


def _profile_summary(p: dict, a: dict) -> str:
    name = p.get("name") or "Your pet"
    age = p.get("age")
    age_txt = f"{age:g}-year-old " if isinstance(age, (int, float)) else ""
    desc = " ".join(str(x) for x in (p.get("breed"), p.get("species")) if x) or "pet"
    weight = f" weighing {p['weight_kg']:g} kg" if p.get("weight_kg") else ""
    text = f"**{name}** is a {age_txt}{desc}{weight} with {p.get('activity_level', 'moderate')} activity."
    if a.get("ready"):
        size = f", {a['size']} size" if a.get("size") else ""
        text += f"\n- Life stage: {a['stage']}{size}."
        text += f"\n- Suggested exercise: about {a['exercise_minutes']} minutes a day."
        for point in a.get("attention_points", []):
            text += f"\n- {point}"
    return text


def general_node(state: PetCareState):
    t = time.time()
    profile = state.get("profile") or state.get("pet") or {}
    name = profile.get("name") or "your pet"
    intent = state.get("intent")
    msg = state.get("user_message", "")

    if state.get("health_concern"):
        reply, how = URGENT_REPLY.format(name=name), "health concern: referred to a vet, no diagnosis"
    elif intent == "pet_profile" and profile:
        reply, how = _profile_summary(profile, state.get("assessment") or {}), "profile summary"
    else:
        answer = llm_text(
            SAFETY_SYSTEM + " Answer in at most four short sentences.",
            f"Pet: {pet_line(profile)}.\nQuestion: {msg}",
        )
        reply, how = (answer, "answered with the language model") if answer else (FALLBACK.format(name=name), "built-in guidance")

    return {
        "results": {"general": {"reply": reply}},
        "reply": reply,
        "completed_agents": ["general"],
        "trace": [make_trace("General Care Agent", how.capitalize(), t)],
    }
