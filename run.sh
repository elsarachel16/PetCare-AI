#!/usr/bin/env bash
# Start PetCare AI: creates a virtual environment on first run, then serves the site at http://localhost:8000
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install -q -r requirements.txt
if command -v ollama >/dev/null 2>&1; then
  ollama list 2>/dev/null | grep -q "qwen2.5:3b" || echo "Tip: run 'ollama pull qwen2.5:3b' for AI-written tips. Running in rules mode until then."
else
  echo "Ollama not found: running in rules mode (all plans still work)."
fi
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
