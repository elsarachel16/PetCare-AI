"""Pet Routing Agent: decides what the user needs.

Keyword rules handle the common cases (fast and predictable). The language
model is only asked when nothing matches.
"""
import re
import time
from typing import Tuple

from llm import llm_json
from state import INTENT_AGENTS, PetCareState, make_trace

HEALTH_CONCERN_RE = re.compile(
    r"\b(vomit\w*|bleed\w*|blood|poison\w*|toxic|seizure\w*|collaps\w*|can'?t breathe|trouble breathing|"
    r"choking|swollen|limp\w*|lethargic|not eating|won'?t eat|diarr?hou?ea|emergency|unresponsive|"
    r"ate (?:chocolate|grapes|xylitol)|hit by (?:a )?car|in pain)\b",
    re.I,
)

EDIT_RE = re.compile(
    r"\b(change|modify|update|adjust|move|swap|skip|reschedule|instead|won'?t be|will not be|can'?t|"
    r"cannot|not (?:at )?home|away|busy|shorter|longer|reduce|increase|\d+\s*min(?:ute)?s?)\b",
    re.I,
)
# Questions only count as follow-ups when they are about the plan itself.
QUESTION_RE = re.compile(r"\b(why|explain|what if)\b", re.I)
PLAN_WORDS_RE = re.compile(r"\b(plan|schedule|walks?|exercise|groom\w*|brush\w*|feed\w*|meals?|routine)\b", re.I)

CREATE_PLAN_RE = re.compile(r"\b(care plan|weekly plan|weekly care|full plan|new plan|routine)\b|"
                            r"\b(create|generate|make|build)\b.*\bplan\b", re.I)

KEYWORDS = {
    "exercise": r"\b(exercise|walks?|run(?:ning)?|play(?:time)?|activity|fetch|workout)\b",
    "grooming": r"\b(groom\w*|brush\w*|bath\w*|nails?|fur\b|coat|shed\w*|haircut|trim\w*|teeth|dental)\b",
    "feeding": r"\b(feed\w*|meals?|food|diet|eat\w*|kibble|treats?|portions?)\b",
    "vaccination_reminder": r"\b(vaccin\w*|booster|shots?|deworm\w*|flea|tick)\b",
    "vet_appointment": r"\b(vet|veterinar\w*|appointments?|check-?up|remind\w*)\b",
    "pet_profile": r"\b(profile|details|weighs?|weight|about my (?:pet|dog|cat|rabbit))\b",
}


def classify(msg: str, has_plan: bool) -> Tuple[str, str]:
    low = msg.lower()
    if HEALTH_CONCERN_RE.search(low):
        return "urgent_health", "health concern keywords"

    wants_new_plan = bool(CREATE_PLAN_RE.search(low))
    is_followup = bool(EDIT_RE.search(low) or (QUESTION_RE.search(low) and PLAN_WORDS_RE.search(low)))
    if has_plan and is_followup and not wants_new_plan and not re.search(r"\b(weight|profile)\b", low):
        return "followup", "modifies the existing plan"
    if wants_new_plan:
        return "care_plan", "asks for a full plan"

    scores = {k: len(re.findall(p, low)) for k, p in KEYWORDS.items()}
    # A date or reminder request should reach the appointment agent even if grooming is mentioned too.
    if scores["vet_appointment"] and scores["grooming"]:
        return "vet_appointment", "appointment and reminder keywords"
    best = max(scores, key=lambda k: scores[k])
    if scores[best] > 0:
        return best, "keyword match"

    data = llm_json(
        "You classify pet-care requests. Reply with JSON like {\"intent\": \"exercise\"}. "
        "Allowed intents: care_plan, exercise, feeding, grooming, vaccination_reminder, "
        "vet_appointment, pet_profile, general_question.",
        msg,
    )
    if data and data.get("intent") in INTENT_AGENTS and data["intent"] not in ("followup", "urgent_health"):
        return data["intent"], "language model"
    return "general_question", "no keyword match"


def routing_node(state: PetCareState):
    t = time.time()
    msg = state.get("user_message", "")
    intent, why = classify(msg, bool(state.get("previous_plan")))
    return {
        "intent": intent,
        "health_concern": intent == "urgent_health",
        "pending_agents": list(INTENT_AGENTS[intent]),
        "trace": [make_trace("Pet Routing Agent", f"Intent: {intent.replace('_', ' ')}", t, reason=why)],
    }
