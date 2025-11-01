import os
import uuid
import asyncio
import traceback
from typing import Dict, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

from utils.sse import sse_pack
from utils.audio import ensure_wav_16k_mono

from pipelines.pipeline_acrcloud import run_acrcloud
from pipelines.pipeline_whisper_genius import run_whisper_genius
from pipelines.pipeline_custom import run_custom
from pipelines.pipeline_genius_text import run_genius_text

router = APIRouter()

# archivio in memoria: token -> path file
UPLOADS: Dict[str, str] = {}


# --- Upload: riceve audio, normalizza in WAV 16k mono e ritorna un token ---
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


# --- SSE: avvia le 3 pipeline e invia card per card ---
@router.get("/identify_stream")
async def identify_stream(token: str = Query(...)):
    if token not in UPLOADS:
        raise HTTPException(status_code=400, detail="Token non valido")
    audio_path = UPLOADS[token]

    async def event_generator():
        # Attiva pipeline secondo variabili di ambiente
        tasks = []
        if os.getenv("ENABLE_ACRCLOUD", "1") == "1":
            tasks.append(asyncio.create_task(run_acrcloud(audio_path)))
        else:
            yield sse_pack("acrcloud", {"source": "acrcloud", "ok": False, "disabled": True})

        if os.getenv("ENABLE_WHISPER_GENIUS", "1") == "1":
            tasks.append(asyncio.create_task(run_whisper_genius(audio_path)))
        else:
            yield sse_pack("whisper_genius", {"source": "whisper_genius", "ok": False, "disabled": True})

        if os.getenv("ENABLE_CUSTOM", "0") == "1":
            tasks.append(asyncio.create_task(run_custom(audio_path)))
        else:
            yield sse_pack("custom", {"source": "custom", "ok": False, "disabled": True})

        TIMEOUT = int(os.getenv("SSE_TIMEOUT_SEC", "45"))
        try:
            start = asyncio.get_event_loop().time()
            while tasks:
                finished, tasks = await asyncio.wait(
                    tasks, timeout=0.1, return_when=asyncio.FIRST_COMPLETED
                )
                for t in finished:
                    try:
                        payload = t.result()
                    except Exception as e:
                        payload = {"source": "internal", "ok": False, "error": str(e)}
                    yield sse_pack(event=payload.get("source", "unknown"), data=payload)

                if asyncio.get_event_loop().time() - start > TIMEOUT:
                    for t in tasks:
                        t.cancel()
                    yield sse_pack("timeout", {"ok": False, "error": "timeout"})
                    break

            yield sse_pack("done", {"ok": True})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            yield sse_pack("internal_error", {"ok": False, "error": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# --- Fallback non-SSE: restituisce tutto insieme (sincrono) ---
@router.post("/identify_all")
async def identify_all(token: Optional[str] = None):
    """
    Esegue tutte le pipeline in parallelo (fallback non streaming).
    Ogni pipeline viene cronometrata individualmente.
    """
    if not token or token not in UPLOADS:
        raise HTTPException(status_code=400, detail="Token non valido")

    audio_path = UPLOADS[token]

    async def safe_run(func, *args):
        """Esegue la pipeline in modo sicuro e misura il tempo di esecuzione."""
        start = asyncio.get_event_loop().time()
        try:
            result = func(*args)
            if asyncio.iscoroutine(result):
                result = await result
            elapsed = round(asyncio.get_event_loop().time() - start, 2)
            if isinstance(result, dict):
                result["elapsed_sec"] = elapsed
            else:
                result = {
                    "source": getattr(func, "__name__", "unknown"),
                    "ok": True,
                    "result": str(result),
                    "elapsed_sec": elapsed,
                }
            return result
        except Exception as e:
            elapsed = round(asyncio.get_event_loop().time() - start, 2)
            return {
                "source": getattr(func, "__name__", "unknown"),
                "ok": False,
                "error": str(e),
                "elapsed_sec": elapsed,
            }

    # Esegue le 3 pipeline in parallelo
    results = await asyncio.gather(
        safe_run(run_acrcloud, audio_path),
        safe_run(run_whisper_genius, audio_path),
        safe_run(run_custom, audio_path),
    )

    ordered = sorted(results, key=lambda r: r.get("source", ""))
    return {"ok": True, "results": ordered}


# --- Ricerca testuale su Genius ---
@router.get("/identify_text")
async def identify_text(query: str):
    """Ricerca testuale su Genius."""
    return await run_genius_text(query)