"""Follow-up ReAct agent (your Phase 5 pattern): create_react_agent + tools + MemorySaver.

One conversation thread per pet, so the assistant remembers earlier questions
("What should I prepare?" ... "And how long should I plan for that?").
Returns None when the model is unavailable so callers can use their fallback.
"""
import warnings
from typing import Optional

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from llm import get_llm, llm_available
from tools.pet_tools import ALL_TOOLS, CURRENT_PLAN_SUMMARY

SYSTEM_PROMPT = (
    "You are PetCare AI's follow-up assistant. Answer questions about a pet's care plan using the "
    "tools. Call current_care_plan first when the question is about the plan. You give general care "
    "information only: never diagnose, never prescribe medication, never state exact food quantities, "
    "and tell the owner to ask a vet about any health concern. Answer in at most four short sentences, "
    "plain text, no markdown."
)

_checkpointer = MemorySaver()
_agent = None


def build_followup_agent(llm=None):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # create_react_agent is being moved in newer langgraph versions
        from langgraph.prebuilt import create_react_agent

        try:
            return create_react_agent(llm or get_llm(), ALL_TOOLS, checkpointer=_checkpointer, prompt=SYSTEM_PROMPT)
        except TypeError:  # older langgraph used state_modifier / messages_modifier
            return create_react_agent(llm or get_llm(), ALL_TOOLS, checkpointer=_checkpointer, state_modifier=SYSTEM_PROMPT)


def ask(agent, thread_id: str, question: str) -> str:
    """Send one question in a thread; the checkpointer keeps earlier turns for that thread."""
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke({"messages": [HumanMessage(content=question)]}, config=config)
    return str(result["messages"][-1].content).strip()


def answer_question(thread_id: str, question: str, plan_summary: str, agent=None) -> Optional[str]:
    """Answer a follow-up question with the ReAct agent. None means 'model not available'."""
    global _agent
    if agent is None:
        if not llm_available():
            return None
        try:
            _agent = _agent or build_followup_agent()
        except Exception:
            return None
        agent = _agent
    token = CURRENT_PLAN_SUMMARY.set(plan_summary)
    try:
        return ask(agent, thread_id, question) or None
    except Exception:
        return None
    finally:
        CURRENT_PLAN_SUMMARY.reset(token)
