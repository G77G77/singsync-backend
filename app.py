import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.main_router import router as main_router

app = FastAPI(title="SingSync Backend", version="4.0")

# CORS aperto (restringi quando pubblichi in produzione)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "SingSync Backend",
        "env": {
            "ENABLE_ACRCLOUD": os.getenv("ENABLE_ACRCLOUD", "1"),
            "ENABLE_WHISPER_GENIUS": os.getenv("ENABLE_WHISPER_GENIUS", "1"),
            "ENABLE_CUSTOM": os.getenv("ENABLE_CUSTOM", "0"),
            "SSE_TIMEOUT_SEC": os.getenv("SSE_TIMEOUT_SEC", "45"),
            "ARCCLOUD_HOST": os.getenv("ARCCLOUD_HOST", ""),
            "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY", "")),
            "GENIUS_API_TOKEN": bool(os.getenv("GENIUS_API_TOKEN", "")),
        }
    }

# Router principale (upload + identify_stream + identify_all)
app.include_router(main_router)