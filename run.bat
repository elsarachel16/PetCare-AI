@echo off
REM Start PetCare AI on Windows. Site opens at http://localhost:8000
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
