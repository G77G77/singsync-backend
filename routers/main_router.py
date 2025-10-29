import os
import uuid
import asyncio
import traceback
from typing import Dict, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

from utils.sse import sse_pack
from utils.audio import ensure_wav_16k_mono

# Import pipeline modulari
from pipelines.pipeline_acrcloud import run_acrcloud
from pipelines.pipeline_whisper_genius import run_whisper_genius
from pipelines.pipeline_custom import run_custom

router = APIRouter()

# Archivio temporaneo in memoria: token → percorso file
UPLOADS: Dict[str, str] = {}

# === UPLOAD AUDIO ===
@router.post("/upload_audio")
async def upload_audio(audio: UploadFile = File(...)):
    """Riceve un file audio, lo converte in WAV 16kHz mono e ritorna un token."""
    try:
        normalized_path = await ensure_wav_16k_mono(audio)
        token = str(uuid.uuid4())[:12]
        UPLOADS[token] = normalized_path
        return {"ok": True, "token": token}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)


# === IDENTIFY STREAM (SSE) ===
@router.get("/identify_stream")
async def identify_stream(token: str = Query(...)):
    """Streaming: invia le tre card (ACRCloud, Whisper+Genius, Custom) man mano che finiscono."""
    if token not in UPLOADS:
        raise HTTPException(status_code=400, detail="Token non valido")

    audio_path = UPLOADS[token]

    async def event_generator():
        TIMEOUT = int(os.getenv("SSE_TIMEOUT_SEC", "60"))

        tasks = []
        if os.getenv("ENABLE_ACRCLOUD", "1") == "1":
            tasks.append(asyncio.create_task(run_acrcloud(audio_path)))
        else:
            yield sse_pack("acrcloud", {"source": "acrcloud", "ok": False, "disabled": True})

        if os.getenv("ENABLE_WHISPER_GENIUS", "1") == "1":
            tasks.append(asyncio.create_task(run_whisper_genius(audio_path)))
        else:
            yield sse_pack("whisper_genius", {"source": "whisper_genius", "ok": False, "disabled": True})

        if os.getenv("ENABLE_CUSTOM", "1") == "1":
            tasks.append(asyncio.create_task(run_custom(audio_path)))
        else:
            yield sse_pack("custom", {"source": "custom", "ok": False, "disabled": True})

        try:
            start = asyncio.get_event_loop().time()
            while tasks:
                done, pending = await asyncio.wait(
                    tasks, timeout=0.2, return_when=asyncio.FIRST_COMPLETED
                )
                for t in done:
                    try:
                        payload = t.result()
                    except Exception as e:
                        payload = {"source": "internal", "ok": False, "error": str(e)}
                    yield sse_pack(event=payload.get("source", "unknown"), data=payload)
                    tasks.remove(t)

                if asyncio.get_event_loop().time() - start > TIMEOUT:
                    for t in tasks:
                        t.cancel()
                    yield sse_pack("timeout", {"ok": False, "error": "timeout"})
                    break

            yield sse_pack("done", {"ok": True})

        except asyncio.CancelledError:
            pass
        except Exception as e:
            traceback.print_exc()
            yield sse_pack("internal_error", {"ok": False, "error": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# === FALLBACK NON-SSE ===
@router.post("/identify_all")
async def identify_all(token: Optional[str] = None):
    """Fallback sincrono: invoca le tre pipeline e restituisce un JSON unico."""
    if not token or token not in UPLOADS:
        raise HTTPException(status_code=400, detail="Token non valido")

    audio_path = UPLOADS[token]
    results = []

    try:
        if os.getenv("ENABLE_ACRCLOUD", "1") == "1":
            results.append(await run_acrcloud(audio_path))
        else:
            results.append({"source": "acrcloud", "ok": False, "disabled": True})

        if os.getenv("ENABLE_WHISPER_GENIUS", "1") == "1":
            results.append(await run_whisper_genius(audio_path))
        else:
            results.append({"source": "whisper_genius", "ok": False, "disabled": True})

        if os.getenv("ENABLE_CUSTOM", "1") == "1":
            results.append(await run_custom(audio_path))
        else:
            results.append({"source": "custom", "ok": False, "disabled": True})

    except Exception as e:
        traceback.print_exc()
        results.append({"source": "internal", "ok": False, "error": str(e)})

    return {"ok": True, "results": results}