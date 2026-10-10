"""Central configuration. Everything can be overridden with environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("PETCARE_DATA_DIR", BASE_DIR / "data"))
REPORTS_DIR = Path(os.getenv("PETCARE_REPORTS_DIR", BASE_DIR / "reports"))
FRONTEND_DIR = BASE_DIR.parent / "frontend"

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.getenv("PETCARE_MODEL", "qwen2.5:3b")

# Set PETCARE_USE_LLM=0 to run with the built-in rules only (fast, no Ollama needed).
USE_LLM = os.getenv("PETCARE_USE_LLM", "1") != "0"

DISCLAIMER = (
    "PetCare AI helps you organise care. It is general information, not veterinary "
    "advice. For health, medication, or diet questions, ask your vet."
)

DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
