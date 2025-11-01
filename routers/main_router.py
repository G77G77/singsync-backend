# routers/main_router.py
import os
import uuid
import asyncio
from typing import Dict, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException

from pipelines.pipeline_whisper_genius import run_whisper_genius
from pipelines.pipeline_acrcloud import run_acrcloud
from pipelines.pipeline_genius_text import run_genius_text
try:
    from pipelines.pipeline_custom import run_custom  # opzionale
except Exception:
    run_custom = None  # type: ignore

router = APIRouter()

# token -> percorso file salvato
UPLOADS: Dict[str, str] = {}

UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def _save_upload(f: UploadFile) -> str:
    token = uuid.uuid4().hex[:8]
    # Manteniamo estensione se presente, altrimenti .m4a
    ext = ""
    if f.filename and "." in f.filename:
        ext = "." + f.filename.split(".")[-1]
    else:
        ext = ".m4a"
    path = os.path.join(UPLOAD_DIR, f"{token}{ext}")

    with open(path, "wb") as out:
        out.write(await f.read())

    UPLOADS[token] = path
    return token


@router.post("/upload_audio")
async def upload_audio(
    audio: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
):
    """
    Accetta file audio dal client.
    Compatibile con campi 'audio' (preferito) o 'file' (fallback).
    Ritorna un token da usare con /identify_all.
    """
    f = audio or file
    if not f:
        raise HTTPException(status_code=422, detail=[{
            "type": "missing", "loc": ["body", "file"], "msg": "Field required", "input": None
        }])

    token = await _save_upload(f)
    return {"ok": True, "token": token}


@router.get("/identify_all")
async def identify_all(token: str):
    """
    Esegue le pipeline abilitate via env:
      - ENABLE_ACRCLOUD (default 1)
      - ENABLE_WHISPER_GENIUS (default 1)
      - ENABLE_CUSTOM (default 0)
    """
    if token not in UPLOADS:
        raise HTTPException(status_code=400, detail="Token non valido")

    path = UPLOADS[token]
    tasks = []

    # ✅ ACRCloud: accetta SOLO file_path
    if os.getenv("ENABLE_ACRCLOUD", "1") == "1":
        tasks.append(run_acrcloud(path))  # <-- FIX: tolto 'token'

    # ✅ Whisper+Genius: accetta SOLO file_path
    if os.getenv("ENABLE_WHISPER_GENIUS", "1") == "1":
        tasks.append(run_whisper_genius(path))

    # ✅ Custom (se presente): lasciamo la firma che avete già
    if os.getenv("ENABLE_CUSTOM", "0") == "1" and run_custom is not None:
        try:
            # Se la vostra custom richiede anche il token, mantenetelo.
            tasks.append(run_custom(token, path))  # type: ignore[arg-type]
        except TypeError:
            # In caso accetti solo file_path, facciamo fallback automatico
            tasks.append(run_custom(path))  # type: ignore[misc]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    parsed = []
    for r in results:
        if isinstance(r, Exception):
            parsed.append({
                "source": "internal",
                "ok": False,
                "error": str(r),
                "elapsed_sec": 0
            })
        else:
            parsed.append(r)

    return {"ok": True, "results": parsed}


@router.get("/identify_text")
async def identify_text(query: str):
    """Ricerca testuale su Genius (ritorna più risultati)."""
    return await run_genius_text(query)