"""Ollama / Qwen2.5:3b wrapper.

Every helper returns None when the model is unavailable, so each agent can fall
back to its rule-based logic. The app therefore works with or without Ollama.
"""
import json
import re
import time
from typing import Any, Dict, Optional

import requests

from config import MODEL_NAME, OLLAMA_HOST, USE_LLM

_status = {"checked": 0.0, "reachable": False, "model_ready": False}
_models: Dict[str, Any] = {}


def llm_status(force: bool = False) -> Dict[str, Any]:
    """Cheap, cached health check for the Ollama server and the configured model."""
    if not USE_LLM:
        return {"enabled": False, "reachable": False, "model_ready": False, "model": MODEL_NAME}
    now = time.time()
    if force or now - _status["checked"] > 20:
        reachable, ready = False, False
        try:
            r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=1.5)
            if r.ok:
                reachable = True
                names = [m.get("name", "") for m in r.json().get("models", [])]
                ready = any(n == MODEL_NAME or n.startswith(MODEL_NAME + ":") for n in names)
        except Exception:
            pass
        _status.update(checked=now, reachable=reachable, model_ready=ready)
    return {
        "enabled": True,
        "reachable": _status["reachable"],
        "model_ready": _status["model_ready"],
        "model": MODEL_NAME,
    }


def llm_available() -> bool:
    s = llm_status()
    return bool(s["enabled"] and s["reachable"] and s["model_ready"])


def get_llm(model: str = MODEL_NAME, temperature: float = 0.0):
    """Same helper as your Trip Concierge llm.py: one place every agent gets its chat model from."""
    from langchain_ollama import ChatOllama

    return ChatOllama(model=model, base_url=OLLAMA_HOST, temperature=temperature, client_kwargs={"timeout": 90})


def _get_model(json_mode: bool = False):
    key = "json" if json_mode else "text"
    if key in _models:
        return _models[key]
    try:
        from langchain_ollama import ChatOllama
    except Exception:
        return None
    kwargs: Dict[str, Any] = dict(
        model=MODEL_NAME,
        base_url=OLLAMA_HOST,
        temperature=0.0 if json_mode else 0.3,
        num_predict=200,
        client_kwargs={"timeout": 90},
    )
    if json_mode:
        kwargs["format"] = "json"
    _models[key] = ChatOllama(**kwargs)
    return _models[key]


def _mark_down():
    _status.update(checked=time.time(), reachable=False, model_ready=False)


def llm_text(system: str, user: str) -> Optional[str]:
    """Return a short plain-text answer, or None if the model is unavailable."""
    if not llm_available():
        return None
    model = _get_model()
    if model is None:
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        out = model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        text = (out.content or "").strip()
        return text or None
    except Exception:
        _mark_down()
        return None


def llm_json(system: str, user: str) -> Optional[Dict[str, Any]]:
    """Return a parsed JSON object, or None if unavailable or unparseable."""
    if not llm_available():
        return None
    model = _get_model(json_mode=True)
    if model is None:
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        out = model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        raw = (out.content or "").strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.S)
            data = json.loads(m.group(0)) if m else None
        return data if isinstance(data, dict) else None
    except Exception:
        _mark_down()
        return None
