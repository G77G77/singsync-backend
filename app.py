import os
import io
import traceback
import tempfile
from typing import Optional

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers.main_router import router as main_router

# ------------------------------
# Configurazione principale FastAPI
# ------------------------------
app = FastAPI(title="SingSync Backend", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in futuro limitare al dominio app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# Variabili d'ambiente
# ------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN")
AUDD_API_TOKEN = os.getenv("AUDD_API_TOKEN")
ARCCLOUD_ACCESS_KEY = os.getenv("ARCCLOUD_ACCESS_KEY")
ARCCLOUD_ACCESS_SECRET = os.getenv("ARCCLOUD_ACCESS_SECRET")
ARCCLOUD_HOST = os.getenv("ARCCLOUD_HOST")

# ------------------------------
# Routing principale
# ------------------------------
app.include_router(main_router)

# ------------------------------
# Health check
# ------------------------------
@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "SingSync Backend",
        "sse": True,
        "whisper_api": bool(OPENAI_API_KEY),
        "genius": bool(GENIUS_API_TOKEN),
        "audd": bool(AUDD_API_TOKEN),
        "acrcloud": bool(ARCCLOUD_ACCESS_KEY),
    }

# ------------------------------
# Error handler globale
# ------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print("❌ Errore globale:", str(exc))
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": str(exc)}
    )