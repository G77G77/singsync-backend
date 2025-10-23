@echo off
echo ==========================================
echo 🚀 Avvio SingSync Backend (Render Dev Local)
echo ==========================================

cd /d "%~dp0"
call venv\Scripts\activate

echo ✅ Ambiente virtuale attivato
echo.
echo 🔥 Avvio server FastAPI su http://127.0.0.1:8000 ...
echo.

python -m uvicorn app:app --reload

pause