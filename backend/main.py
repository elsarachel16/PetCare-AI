"""PetCare AI API server. Run from the backend folder:  uvicorn main:app --reload"""
import logging
from datetime import date
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

import reports
from config import FRONTEND_DIR
from graph.petcare_graph import GRAPH
from llm import llm_status
from storage import Store

log = logging.getLogger("petcare")
store = Store()
app = FastAPI(title="PetCare AI", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------- models ----------
class PetIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    species: Literal["dog", "cat", "rabbit", "bird", "hamster", "guinea pig", "other"] = "dog"
    breed: str = Field("", max_length=60)
    age: float = Field(1, ge=0, le=40)
    weight_kg: float = Field(10, gt=0, le=200)
    activity_level: Literal["low", "moderate", "high"] = "moderate"
    notes: str = Field("", max_length=500)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    pet_id: Optional[str] = None


class ReminderIn(BaseModel):
    pet_id: str
    title: str = Field(min_length=1, max_length=120)
    due_date: str
    category: Literal["general", "health", "grooming", "exercise", "feeding"] = "general"
    repeat_weeks: Optional[int] = Field(None, ge=1, le=52)

    @field_validator("due_date")
    @classmethod
    def _valid_date(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("due_date must look like 2026-10-20")
        return v


# ---------- health ----------
@app.get("/api/health")
def health():
    return {"status": "ok", "llm": llm_status()}


@app.get("/api/graph")
def graph_diagram():
    try:
        return {"mermaid": GRAPH.get_graph().draw_mermaid()}
    except Exception:  # drawing is optional
        return {"mermaid": ""}


# ---------- pets ----------
@app.get("/api/pets")
def list_pets():
    return store.list_pets()


@app.post("/api/pets", status_code=201)
def create_pet(pet: PetIn):
    return store.create_pet(pet.model_dump())


@app.put("/api/pets/{pet_id}")
def update_pet(pet_id: str, pet: PetIn):
    updated = store.update_pet(pet_id, pet.model_dump())
    if not updated:
        raise HTTPException(404, "Pet not found.")
    return updated


@app.delete("/api/pets/{pet_id}", status_code=204)
def delete_pet(pet_id: str):
    if not store.delete_pet(pet_id):
        raise HTTPException(404, "Pet not found.")


@app.get("/api/pets/{pet_id}/plan")
def get_plan(pet_id: str):
    if not store.get_pet(pet_id):
        raise HTTPException(404, "Pet not found.")
    return store.get_plan(pet_id)


# ---------- chat (runs the agent graph) ----------
@app.post("/api/chat")
def chat(body: ChatIn):
    pet = None
    if body.pet_id:
        pet = store.get_pet(body.pet_id)
        if not pet:
            raise HTTPException(404, "Pet not found.")

    state = {
        "user_message": body.message.strip(),
        "pet_id": body.pet_id,
        "pet": pet or {},
        "previous_plan": store.get_plan(body.pet_id) if pet else None,
        "trace": [],
    }
    try:
        result = GRAPH.invoke(state)
    except Exception:
        log.exception("Agent graph failed")
        raise HTTPException(500, "The care agents hit an error. Check the server log for details.")

    plan = result.get("care_plan")
    if pet and plan:
        store.save_plan(pet["id"], plan)
    if pet and result.get("profile_updates"):
        store.update_pet(pet["id"], result["profile_updates"])

    created = []
    if pet:
        for res in (result.get("results") or {}).values():
            for r in res.get("reminders_to_create", []) if isinstance(res, dict) else []:
                created.append(store.add_reminder(pet["id"], r["title"], r["due_date"], r.get("category", "general"), r.get("repeat_weeks")))

    return {
        "intent": result.get("intent"),
        "reply": result.get("reply", ""),
        "care_plan": plan,
        "changes": result.get("plan_changes", []),
        "profile_updates": result.get("profile_updates", {}),
        "reminders_created": len(created),
        "trace": result.get("trace", []),
        "report_id": (result.get("report") or {}).get("id"),
        "llm": llm_status(),
    }


# ---------- reminders ----------
@app.get("/api/reminders")
def list_reminders(pet_id: Optional[str] = None, include_done: bool = False):
    return store.list_reminders(pet_id, include_done)


@app.post("/api/reminders", status_code=201)
def add_reminder(r: ReminderIn):
    if not store.get_pet(r.pet_id):
        raise HTTPException(404, "Pet not found.")
    return store.add_reminder(r.pet_id, r.title.strip(), r.due_date, r.category, r.repeat_weeks)


@app.post("/api/reminders/{rem_id}/done")
def done_reminder(rem_id: str):
    rem = store.complete_reminder(rem_id)
    if not rem:
        raise HTTPException(404, "Reminder not found.")
    return rem


@app.delete("/api/reminders/{rem_id}", status_code=204)
def delete_reminder(rem_id: str):
    if not store.delete_reminder(rem_id):
        raise HTTPException(404, "Reminder not found.")


# ---------- reports ----------
@app.get("/api/reports")
def list_reports(limit: int = Query(50, ge=1, le=200)):
    return reports.list_reports(limit)


@app.get("/api/reports/{report_id}")
def get_report(report_id: str):
    data = reports.load_report(report_id)
    if data is None:
        raise HTTPException(404, "Report not found.")
    return data


@app.get("/api/reports/{report_id}/download")
def download_report(report_id: str):
    p = reports.report_path(report_id)
    if not p:
        raise HTTPException(404, "Report not found.")
    return FileResponse(p, media_type="application/json", filename=f"{report_id}.json")


# ---------- website ----------
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
