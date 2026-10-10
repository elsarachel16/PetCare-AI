"""The PetCare AI LangGraph workflow.

    routing -> (followup | profile_extraction -> care_assessment -> supervisor)
    supervisor <-> specialist agents (exercise, grooming, feeding, appointment, general)
    supervisor -> recommendation -> report_writer -> END
    followup -> report_writer -> END
"""
from langgraph.graph import END, StateGraph

from agents.appointment import appointment_node
from agents.care_assessment import care_assessment_node
from agents.exercise import exercise_node
from agents.feeding import feeding_node
from agents.followup import followup_node
from agents.general import general_node
from agents.grooming import grooming_node
from agents.pet_profile import pet_profile_node
from agents.recommendation import recommendation_node
from agents.report import report_node
from agents.routing import routing_node
from agents.supervisor import supervisor_node
from state import PetCareState

SPECIALISTS = {
    "exercise": exercise_node,
    "grooming": grooming_node,
    "feeding": feeding_node,
    "appointment": appointment_node,
    "general": general_node,
}


def _after_routing(state: PetCareState) -> str:
    return "followup" if state.get("intent") == "followup" else "profile_extraction"


def _after_supervisor(state: PetCareState) -> str:
    return state["next_agent"]


def build_graph():
    g = StateGraph(PetCareState)
    g.add_node("routing", routing_node)
    g.add_node("profile_extraction", pet_profile_node)
    g.add_node("care_assessment", care_assessment_node)
    g.add_node("supervisor", supervisor_node)
    for name, fn in SPECIALISTS.items():
        g.add_node(name, fn)
    g.add_node("recommendation", recommendation_node)
    g.add_node("followup", followup_node)
    g.add_node("report_writer", report_node)

    g.set_entry_point("routing")
    g.add_conditional_edges("routing", _after_routing, {"followup": "followup", "profile_extraction": "profile_extraction"})
    g.add_edge("profile_extraction", "care_assessment")
    g.add_edge("care_assessment", "supervisor")
    g.add_conditional_edges(
        "supervisor", _after_supervisor,
        {**{name: name for name in SPECIALISTS}, "recommendation": "recommendation"},
    )
    for name in SPECIALISTS:
        g.add_edge(name, "supervisor")
    g.add_edge("recommendation", "report_writer")
    g.add_edge("followup", "report_writer")
    g.add_edge("report_writer", END)
    return g.compile()


GRAPH = build_graph()
