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

REM If a previous copy is still holding the port, stop it. A stale server keeps the
REM old routes in memory and makes the new UI fail with a 405 — this prevents that.
for /f "tokens=5" %%p in ('netstat -ano ^| findstr "127.0.0.1:8765" ^| findstr "LISTENING"') do (
  echo Stopping a previous Gradian Match still running on port 8765 ^(PID %%p^)...
  taskkill /F /PID %%p >nul 2>&1
)

echo Starting Gradian Match at http://127.0.0.1:8765
start "" http://127.0.0.1:8765
python -m uvicorn gradianmatch.server:app --host 127.0.0.1 --port 8765
