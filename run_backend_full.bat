@echo off
echo ==========================================
echo 🚀 AVVIO COMPLETO SINGSYNC BACKEND
echo ==========================================
cd /d "%~dp0"

REM === 1️⃣ Attiva il virtual environment ===
if not exist "venv\" (
    echo ⚙️  Creazione ambiente virtuale...
    python -m venv venv
)
call venv\Scripts\activate

REM === 2️⃣ Installa le dipendenze ===
echo 📦 Aggiornamento pacchetti...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt >nul

REM === 3️⃣ Git pull per aggiornare ===
echo 🔄 Aggiornamento repository da GitHub...
git pull

REM === 4️⃣ Git commit & push automatico ===
echo 💾 Eseguo commit e push automatico...
git add .
git commit -m "Auto-update locale SingSync backend" >nul 2>&1
git push origin main

REM === 5️⃣ Avvio del server ===
echo ==========================================
echo 🔥 Avvio FastAPI su http://127.0.0.1:8000 ...
echo ==========================================
python -m uvicorn app:app --reload

pause