from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.main_router import router as main_router

app = FastAPI(title="SingSync Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(main_router)

@app.get("/health")
async def health():
    import os
    env = {
        "ENABLE_ACRCLOUD": os.getenv("ENABLE_ACRCLOUD"),
        "ENABLE_WHISPER_GENIUS": os.getenv("ENABLE_WHISPER_GENIUS"),
        "ENABLE_CUSTOM": os.getenv("ENABLE_CUSTOM"),
        "SSE_TIMEOUT_SEC": os.getenv("SSE_TIMEOUT_SEC"),
        "ACRCLOUD_HOST": os.getenv("ACRCLOUD_HOST"),
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
        "GENIUS_API_TOKEN": bool(os.getenv("GENIUS_API_TOKEN")),
    }
    return {"ok": True, "service": "SingSync Backend", "env": env}