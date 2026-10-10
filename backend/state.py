"""Shared state passed between all agents in the LangGraph workflow."""
import operator
import time
from typing import Annotated, Any, Dict, List, Optional, TypedDict


def merge_dicts(a: Optional[dict], b: Optional[dict]) -> dict:
    out = dict(a or {})
    out.update(b or {})
    return out


# Which specialist agents the supervisor queues for each intent.
INTENT_AGENTS: Dict[str, List[str]] = {
    "care_plan": ["exercise", "grooming", "feeding", "appointment"],
    "exercise": ["exercise"],
    "feeding": ["feeding"],
    "grooming": ["grooming"],
    "vaccination_reminder": ["appointment"],
    "vet_appointment": ["appointment"],
    "pet_profile": ["general"],
    "general_question": ["general"],
    "urgent_health": ["general"],
    "followup": [],
}

AGENT_LABELS = {
    "exercise": "Exercise Agent",
    "grooming": "Grooming Agent",
    "feeding": "Feeding Agent",
    "appointment": "Appointment & Reminder Agent",
    "general": "General Care Agent",
    "recommendation": "Care Plan Agent",
}


class PetCareState(TypedDict, total=False):
    # input
    user_message: str
    pet_id: Optional[str]
    pet: Dict[str, Any]
    previous_plan: Optional[Dict[str, Any]]
    # routing / extraction / assessment
    intent: str
    health_concern: bool
    profile: Dict[str, Any]
    profile_updates: Dict[str, Any]
    constraints: Dict[str, Any]
    assessment: Dict[str, Any]
    # supervisor loop
    pending_agents: List[str]
    next_agent: str
    completed_agents: Annotated[List[str], operator.add]
    results: Annotated[Dict[str, Any], merge_dicts]
    # output
    care_plan: Optional[Dict[str, Any]]
    plan_changes: List[str]
    reply: str
    report: Dict[str, Any]
    trace: Annotated[List[Dict[str, Any]], operator.add]


def make_trace(agent: str, summary: str, started: Optional[float] = None, **detail) -> Dict[str, Any]:
    """One entry in the agent activity log shown in the UI and saved in the report."""
    ms = int((time.time() - started) * 1000) if started else 0
    return {"agent": agent, "status": "done", "summary": summary, "ms": ms, "detail": detail}
