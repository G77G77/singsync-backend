import os
import uuid
import asyncio
import traceback
from typing import Dict

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

from utils.sse import sse_pack
from utils.audio import ensure_wav_16k_mono

from pipelines.pipeline_acrcloud import run_acrcloud
from pipelines.pipeline_whisper_genius import run_whisper_genius
from pipelines.pipeline_custom import run_custom

# ✅ Router definito prima di tutto
router = APIRouter()

# archivio in memoria: token -> path file
UPLOADS: Dict[str, str] = {}

# --- Upload audio ---
@router.post("/upload_audio")
async def upload_audio(audio: UploadFile = File(...)):
    try:
        normalized_path = await ensure_wav_16k_mono(audio)
        token = str(uuid.uuid4())[:12]
        UPLOADS[token] = normalized_path
        return {"ok": True, "token": token}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)

# --- SSE streaming ---
@router.get("/identify_stream")
async def identify_stream(token: str = Query(...)):
    if token not in UPLOADS:
        raise HTTPException(status_code=400, detail="Token non valido")
    audio_path = UPLOADS[token]

    async def event_generator():
        TIMEOUT = int(os.getenv("SSE_TIMEOUT_SEC", "45"))
        tasks = []

        if os.getenv("ENABLE_ACRCLOUD", "1") == "1":
            tasks.append(asyncio.create_task(run_acrcloud(token, audio_path)))

        if os.getenv("ENABLE_WHISPER_GENIUS", "1") == "1":
            tasks.append(asyncio.create_task(run_whisper_genius(audio_path)))

        if os.getenv("ENABLE_CUSTOM", "0") == "1":
            tasks.append(asyncio.create_task(run_custom(token, audio_path)))

        start = asyncio.get_event_loop().time()

        try:
            while tasks:
                done, pending = await asyncio.wait(
                    tasks, timeout=0.1, return_when=asyncio.FIRST_COMPLETED
                )
                for t in done:
                    try:
                        payload = t.result()
                    except Exception as e:
                        payload = {"source": "internal", "ok": False, "error": str(e)}

                    yield sse_pack(event=payload.get("source", "unknown"), data=payload)

                # Timeout hard
                if asyncio.get_event_loop().time() - start > TIMEOUT:
                    for t in tasks:
                        t.cancel()
                    yield sse_pack(
                        event="timeout", data={"ok": False, "error": "timeout"}
                    )
                    break

            # Evento finale
            yield sse_pack(event="done", data={"ok": True})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            yield sse_pack(
                event="internal_error", data={"ok": False, "error": str(e)}
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Fallback non-SSE ---
@router.get("/identify_all")
async def identify_all(token: str):
    """Esegue tutte le pipeline (whisper, acrcloud, custom)."""
    if token not in UPLOADS:
        raise HTTPException(status_code=400, detail="Token non valido")

    path = UPLOADS[token]
    tasks = []

    # ✅ ACRCloud
    if os.getenv("ENABLE_ACRCLOUD", "1") == "1":
        tasks.append(run_acrcloud(token, path))

    # ✅ Whisper + Genius → solo file_path
    if os.getenv("ENABLE_WHISPER_GENIUS", "1") == "1":
        tasks.append(run_whisper_genius(path))

    # ✅ Custom
    if os.getenv("ENABLE_CUSTOM", "0") == "1":
        tasks.append(run_custom(token, path))

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