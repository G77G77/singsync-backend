@echo on
title SingSync Backend - DEBUG MODE
echo ================================================
echo     🔍 AVVIO DEBUG SINGSYNC BACKEND
echo ================================================
echo.

REM --- 1️⃣ Controllo directory ---
echo [DEBUG] Directory corrente:
cd
echo.

REM --- 2️⃣ Attivazione virtual env ---
echo [DEBUG] Attivazione virtual environment...
call venv\Scripts\activate
if errorlevel 1 (
    echo ❌ ERRORE: impossibile attivare venv. Controlla che esista la cartella "venv".
    pause
    exit /b
)
echo ✅ venv attivato correttamente.
echo.

REM --- 3️⃣ Controllo moduli Python ---
echo [DEBUG] Controllo moduli installati...
python -m pip list
echo.

REM --- 4️⃣ Test import principale ---
echo [DEBUG] Test import FastAPI...
python -c "import fastapi, requests, numpy, librosa; print('✅ Import OK')" || (
    echo ❌ ERRORE: uno o più pacchetti mancanti.
    pause
    exit /b
)
echo.

REM --- 5️⃣ Avvio backend con log in tempo reale ---
echo [DEBUG] Avvio server FastAPI con Uvicorn...
set LOGFILE=logs\backend_debug_log.txt
if not exist logs mkdir logs
echo Scrittura log su: %LOGFILE%
echo.

python -m uvicorn app:app --reload
if errorlevel 1 (
    echo ❌ Uvicorn non è stato trovato o ha generato errore.
    echo Prova a installarlo con: pip install uvicorn fastapi
    pause
    exit /b
)

echo.
echo ✅ Backend terminato correttamente.
pause