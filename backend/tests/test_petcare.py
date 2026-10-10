"""Run from the backend folder:  pytest -q
Tests run with the language model switched off, so they need no Ollama."""
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["PETCARE_USE_LLM"] = "0"
os.environ["PETCARE_DATA_DIR"] = _tmp
os.environ["PETCARE_REPORTS_DIR"] = str(Path(_tmp) / "reports")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from agents.routing import classify  # noqa: E402
from main import app  # noqa: E402
from tools.pet_calculator import assess  # noqa: E402
from tools.reminders import parse_date, parse_interval_weeks  # noqa: E402
from tools.text_parsing import extract_constraints, extract_days, extract_pet_fields  # noqa: E402

client = TestClient(app)

BRUNO = {"name": "Bruno", "species": "dog", "breed": "Labrador", "age": 3, "weight_kg": 24, "activity_level": "moderate"}


@pytest.fixture(scope="module")
def bruno():
    return client.post("/api/pets", json=BRUNO).json()


# ---------- unit tests ----------
def test_routing_intents():
    assert classify("My dog needs a grooming schedule.", False)[0] == "grooming"
    assert classify("Create a weekly care plan for Bruno.", False)[0] == "care_plan"
    assert classify("Help me organize Bruno's feeding schedule", False)[0] == "feeding"
    assert classify("Next vet appointment 20 October, grooming every 4 weeks", False)[0] == "vet_appointment"
    assert classify("I won't be home on Wednesday. Change the exercise plan.", True)[0] == "followup"
    assert classify("He has been vomiting since last night", True)[0] == "urgent_health"


def test_parsers():
    assert extract_days("I won't be home on Wednesday and the weekend") == ["Wednesday", "Saturday", "Sunday"]
    f = extract_pet_fields("my 3-year-old Labrador dog weighs 24 kg")
    assert f["species"] == "dog" and f["breed"] == "Labrador" and f["age"] == 3 and f["weight_kg"] == 24
    assert parse_interval_weeks("every 4 weeks") == 4
    assert parse_date("2026-10-20") == date(2026, 10, 20)
    assert parse_date("on 20 October", today=date(2026, 9, 19)) == date(2026, 10, 20)
    c = extract_constraints("Next vet appointment 20 October. Grooming every 4 weeks.")
    assert c["appointments"][0]["title"] == "Vet appointment" and c["grooming_interval_weeks"] == 4


def test_assessment():
    a = assess(BRUNO)
    assert a["ready"] and a["stage"] == "adult" and a["size"] == "medium"
    assert a["brushing_per_week"] == 3 and a["meals_per_day"] == 2
    assert assess({"species": "dog", "breed": "Pug", "age": 3, "weight_kg": 8})["exercise_minutes"] <= 30
    assert assess({})["ready"] is False


# ---------- API flow ----------
def test_health():
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["llm"]["enabled"] is False


def test_pet_validation():
    assert client.post("/api/pets", json={"name": "", "species": "dog"}).status_code == 422
    assert client.post("/api/pets", json={"name": "X", "species": "dragon"}).status_code == 422


def test_full_care_plan_and_followup(bruno):
    r = client.post("/api/chat", json={"message": "Create a weekly care plan for Bruno.", "pet_id": bruno["id"]}).json()
    assert r["intent"] == "care_plan"
    plan = r["care_plan"]
    assert set(plan["week"]) >= {"Monday", "Sunday"}
    assert plan["exercise"]["daily_minutes"] > 0 and plan["feeding"]["meals_per_day"] == 2
    agents = [t["agent"] for t in r["trace"]]
    for name in ("Pet Routing Agent", "Pet Profile Extraction Agent", "Care Assessment Agent", "Supervisor Agent",
                 "Exercise Agent", "Grooming Agent", "Feeding Agent", "Care Plan Agent", "Report Agent"):
        assert name in agents
    assert r["report_id"] and client.get(f"/api/reports/{r['report_id']}").status_code == 200

    # follow-up edits the saved plan
    f = client.post("/api/chat", json={"message": "I won't be home on Wednesday. Change Bruno's exercise plan.", "pet_id": bruno["id"]}).json()
    assert f["intent"] == "followup" and f["changes"]
    wed = f["care_plan"]["exercise"]["week"]["Wednesday"]
    assert wed["away"] is True
    assert f["care_plan"]["revision"] == 2
    assert any("Away day" in t["task"] for t in f["care_plan"]["week"]["Wednesday"])
    assert client.get(f"/api/pets/{bruno['id']}/plan").json()["exercise"]["unavailable_days"] == ["Wednesday"]

    # duration change
    g = client.post("/api/chat", json={"message": "Make the walks 20 minutes longer", "pet_id": bruno["id"]}).json()
    assert g["intent"] == "followup" and g["care_plan"]["exercise"]["daily_minutes"] == plan["exercise"]["daily_minutes"] + 20


def test_appointment_creates_reminders(bruno):
    msg = f"Next vet appointment {(date.today() + timedelta(days=30)).isoformat()}, grooming every 4 weeks"
    r = client.post("/api/chat", json={"message": msg, "pet_id": bruno["id"]}).json()
    assert r["intent"] == "vet_appointment" and r["reminders_created"] >= 2
    titles = [x["title"] for x in client.get("/api/reminders", params={"pet_id": bruno["id"]}).json()]
    assert any("Vet appointment" in t for t in titles) and any("Grooming" in t for t in titles)
    # same message again does not duplicate
    client.post("/api/chat", json={"message": msg, "pet_id": bruno["id"]})
    again = client.get("/api/reminders", params={"pet_id": bruno["id"]}).json()
    assert len(again) == len(titles)


def test_health_concern_is_not_diagnosed(bruno):
    r = client.post("/api/chat", json={"message": "Bruno keeps vomiting and won't eat", "pet_id": bruno["id"]}).json()
    assert r["intent"] == "urgent_health" and r["care_plan"] is None
    assert "vet" in r["reply"].lower() and "diagnos" in r["reply"].lower()


def test_no_profile_asks_for_details():
    r = client.post("/api/chat", json={"message": "Create a weekly care plan"}).json()
    assert r["care_plan"] is None and "details" in r["reply"].lower()


def test_reminder_lifecycle(bruno):
    due = date.today().isoformat()
    rem = client.post("/api/reminders", json={"pet_id": bruno["id"], "title": "Flea treatment", "due_date": due, "repeat_weeks": 4}).json()
    done = client.post(f"/api/reminders/{rem['id']}/done").json()
    assert done["due_date"] > due and not done["done"]
    assert client.delete(f"/api/reminders/{rem['id']}").status_code == 204
    assert client.post("/api/reminders", json={"pet_id": bruno["id"], "title": "x", "due_date": "nope"}).status_code == 422


def test_report_id_is_safe():
    assert client.get("/api/reports/..%2f..%2fetc%2fpasswd").status_code == 404


# ---------- Trip-Concierge-style tool agent (scripted fake model, no Ollama) ----------
def test_tools():
    from tools.pet_tools import care_calculator, pet_care_info
    assert "150" in care_calculator.invoke({"expression": "30 min * 5 days"})
    assert "52.9" in care_calculator.invoke({"expression": "24 kg to lb"})
    assert "next on" in care_calculator.invoke({"expression": "every 4 weeks from 2026-10-01"})
    assert "Dog" in pet_care_info.invoke({"species": "dog"})


def test_react_followup_agent_uses_plan_tool():
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage

    from agents.followup_agent import answer_question, build_followup_agent

    class FakeToolModel(GenericFakeChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    call = AIMessage(content="", tool_calls=[{"name": "current_care_plan", "args": {"question_topic": ""}, "id": "c1"}])
    final = AIMessage(content="Wednesday is an away day, so the walks move to Thursday and Friday.")
    agent = build_followup_agent(FakeToolModel(messages=iter([call, final])))
    reply = answer_question("pet-test", "Why did Wednesday change?", "away days: Wednesday", agent=agent)
    assert reply and "Wednesday" in reply
