@echo off
setlocal enabledelayedexpansion

:: === Timestamp per log ===
for /f "tokens=1-4 delims=/ " %%a in ("%date%") do (
    set DATESTAMP=%%d-%%b-%%c
)
for /f "tokens=1-2 delims=: " %%a in ("%time%") do (
    set TIMESTAMP=%%a%%b
)
set LOGFILE=logs\backend_run_%DATESTAMP%_%TIMESTAMP%.log

echo ========================================== > %LOGFILE%
echo 🚀 AVVIO COMPLETO SINGSYNC BACKEND >> %LOGFILE%
echo ========================================== >> %LOGFILE%
cd /d "%~dp0"

:: === 1️⃣ Crea ambiente virtuale se mancante ===
if not exist "venv\" (
    echo ⚙️  Creazione ambiente virtuale... >> %LOGFILE%
    python -m venv venv >> %LOGFILE% 2>&1
)
call venv\Scripts\activate >> %LOGFILE% 2>&1

:: === 2️⃣ Installa dipendenze ===
echo 📦 Aggiornamento pacchetti... >> %LOGFILE%
python -m pip install --upgrade pip >> %LOGFILE% 2>&1
pip install -r requirements.txt >> %LOGFILE% 2>&1

:: === 3️⃣ Aggiorna repo ===
echo 🔄 Aggiornamento repository da GitHub... >> %LOGFILE%
git pull >> %LOGFILE% 2>&1

:: === 4️⃣ Commit & Push automatico ===
echo 💾 Eseguo commit e push automatico... >> %LOGFILE%
git add . >> %LOGFILE% 2>&1
git commit -m "Auto-update locale SingSync backend" >> %LOGFILE% 2>&1
git push origin main >> %LOGFILE% 2>&1

:: === 5️⃣ Avvio del server FastAPI ===
echo ========================================== >> %LOGFILE%
echo 🔥 Avvio FastAPI su http://127.0.0.1:8000 ... >> %LOGFILE%
echo ========================================== >> %LOGFILE%
echo.
echo 👀 Apri questo file per vedere i log: %LOGFILE%
echo.

:: --- Apre automaticamente il log in Notepad con 5 secondi di ritardo ---
timeout /t 5 /nobreak >nul
start notepad "%LOGFILE%"

python -m uvicorn app:app --reload >> %LOGFILE% 2>&1

pause