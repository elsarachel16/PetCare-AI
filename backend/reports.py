"""Saving and reading JSON pet care reports."""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import REPORTS_DIR

_ID_RE = re.compile(r"^[a-z0-9_-]{3,80}$")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "pet").lower()).strip("-") or "pet"


def save_report(report: Dict[str, Any]) -> str:
    name = _slug((report.get("pet") or {}).get("name", "pet"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_id = f"{name}-{stamp}-{uuid.uuid4().hex[:4]}"
    report["id"] = report_id
    with open(REPORTS_DIR / f"{report_id}.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return report_id


def report_path(report_id: str) -> Optional[Path]:
    if not _ID_RE.match(report_id):
        return None
    p = REPORTS_DIR / f"{report_id}.json"
    return p if p.exists() else None


def load_report(report_id: str) -> Optional[Dict[str, Any]]:
    p = report_path(report_id)
    if not p:
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def list_reports(limit: int = 50) -> List[Dict[str, Any]]:
    items = []
    for p in sorted(REPORTS_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            with open(p, "r", encoding="utf-8") as f:
                r = json.load(f)
            items.append({
                "id": r.get("id", p.stem),
                "created_at": r.get("created_at", ""),
                "pet_name": (r.get("pet") or {}).get("name", ""),
                "request": r.get("request", ""),
                "intent": r.get("intent", ""),
            })
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(items, key=lambda x: x["created_at"], reverse=True)
