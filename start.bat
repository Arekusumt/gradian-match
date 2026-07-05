@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\" (
  echo First run: creating virtual environment and installing dependencies...
  py -3 -m venv .venv || python -m venv .venv
  call ".venv\Scripts\activate.bat"
  python -m pip install --upgrade pip >nul
  python -m pip install -r requirements.txt
) else (
  call ".venv\Scripts\activate.bat"
)
set PYTHONPATH=src
echo Starting Gradian Match at http://127.0.0.1:8765
start "" http://127.0.0.1:8765
python -m uvicorn gradianmatch.server:app --host 127.0.0.1 --port 8765
