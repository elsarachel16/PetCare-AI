"""Supervisor Agent: dispatches the queued specialist agents one at a time, then hands off to the planner."""
import time

from state import AGENT_LABELS, PetCareState, make_trace

NO_PROFILE_OK = ("general_question", "urgent_health", "pet_profile")


def supervisor_node(state: PetCareState):
    t = time.time()
    pending = list(state.get("pending_agents") or [])
    ready = (state.get("assessment") or {}).get("ready", False)

    if not ready and state.get("intent") not in NO_PROFILE_OK:
        pending = []  # cannot plan without knowing the pet

    if pending:
        nxt = pending.pop(0)
        more = f", {len(pending)} more queued" if pending else ""
        summary = f"Dispatched {AGENT_LABELS[nxt]}{more}"
        return {"next_agent": nxt, "pending_agents": pending, "trace": [make_trace("Supervisor Agent", summary, t)]}

    done = [AGENT_LABELS[a] for a in state.get("completed_agents", [])]
    summary = f"Specialists finished ({', '.join(done)}); handing over to the Care Plan Agent" if done else \
        "No specialist could run; handing over to the Care Plan Agent"
    return {"next_agent": "recommendation", "pending_agents": [], "trace": [make_trace("Supervisor Agent", summary, t)]}
