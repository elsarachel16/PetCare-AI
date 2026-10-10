"""Tiny JSON-file store for pets, plans and reminders (thread-safe, no database needed)."""
import json
import os
import threading
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import DATA_DIR
from tools.reminders import next_due


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or DATA_DIR / "db.json")
        self.lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"pets": {}, "plans": {}, "reminders": {}})

    # ---- low level -------------------------------------------------
    def _read(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}
        for key in ("pets", "plans", "reminders"):
            data.setdefault(key, {})
        return data

    def _write(self, data: Dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    # ---- pets ------------------------------------------------------
    def list_pets(self) -> List[Dict[str, Any]]:
        with self.lock:
            return sorted(self._read()["pets"].values(), key=lambda p: p["created_at"])

    def get_pet(self, pet_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            return self._read()["pets"].get(pet_id)

    def create_pet(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            data = self._read()
            pet = {**fields, "id": uuid.uuid4().hex[:8], "created_at": _now()}
            data["pets"][pet["id"]] = pet
            self._write(data)
            return pet

    def update_pet(self, pet_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self.lock:
            data = self._read()
            if pet_id not in data["pets"]:
                return None
            data["pets"][pet_id].update(fields)
            self._write(data)
            return data["pets"][pet_id]

    def delete_pet(self, pet_id: str) -> bool:
        with self.lock:
            data = self._read()
            if pet_id not in data["pets"]:
                return False
            del data["pets"][pet_id]
            data["plans"].pop(pet_id, None)
            data["reminders"] = {k: v for k, v in data["reminders"].items() if v["pet_id"] != pet_id}
            self._write(data)
            return True

    # ---- plans -----------------------------------------------------
    def get_plan(self, pet_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            return self._read()["plans"].get(pet_id)

    def save_plan(self, pet_id: str, plan: Dict[str, Any]) -> None:
        with self.lock:
            data = self._read()
            data["plans"][pet_id] = plan
            self._write(data)

    # ---- reminders -------------------------------------------------
    def list_reminders(self, pet_id: Optional[str] = None, include_done: bool = False) -> List[Dict[str, Any]]:
        with self.lock:
            items = list(self._read()["reminders"].values())
        if pet_id:
            items = [r for r in items if r["pet_id"] == pet_id]
        if not include_done:
            items = [r for r in items if not r.get("done")]
        return sorted(items, key=lambda r: r["due_date"])

    def add_reminder(self, pet_id: str, title: str, due_date: str, category: str = "general",
                     repeat_weeks: Optional[int] = None) -> Dict[str, Any]:
        with self.lock:
            data = self._read()
            for r in data["reminders"].values():
                if r["pet_id"] == pet_id and r["title"] == title and r["due_date"] == due_date and not r.get("done"):
                    return r
            rem = {
                "id": uuid.uuid4().hex[:8], "pet_id": pet_id, "title": title, "due_date": due_date,
                "category": category, "repeat_weeks": repeat_weeks, "done": False, "created_at": _now(),
            }
            data["reminders"][rem["id"]] = rem
            self._write(data)
            return rem

    def complete_reminder(self, rem_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            data = self._read()
            rem = data["reminders"].get(rem_id)
            if not rem:
                return None
            if rem.get("repeat_weeks"):
                rem["last_done"] = date.today().isoformat()
                rem["due_date"] = next_due(date.fromisoformat(rem["due_date"]), rem["repeat_weeks"]).isoformat()
            else:
                rem["done"] = True
            self._write(data)
            return rem

    def delete_reminder(self, rem_id: str) -> bool:
        with self.lock:
            data = self._read()
            if rem_id not in data["reminders"]:
                return False
            del data["reminders"][rem_id]
            self._write(data)
            return True
