"""Report Agent: saves a JSON pet care report for every run."""
import time
from datetime import datetime

from config import DISCLAIMER
from reports import save_report
from state import PetCareState, make_trace


def report_node(state: PetCareState):
    t = time.time()
    entry = make_trace("Report Agent", "Saved pet care report", t)
    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "request": state.get("user_message", ""),
        "intent": state.get("intent"),
        "pet": state.get("profile") or state.get("pet") or {},
        "assessment": state.get("assessment"),
        "care_plan": state.get("care_plan"),
        "reply": state.get("reply"),
        "plan_changes": state.get("plan_changes", []),
        "agent_trace": list(state.get("trace", [])) + [entry],
        "disclaimer": DISCLAIMER,
    }
    report_id = save_report(report)
    entry["summary"] = f"Saved pet care report {report_id}"
    return {"report": {"id": report_id}, "trace": [entry]}
