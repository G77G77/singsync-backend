import os
import uuid
import asyncio
import traceback
from typing import Dict, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Query
from fastapi.responses import JSONResponse, StreamingResponse

from utils.sse import sse_pack
from utils.audio import ensure_wav_16k_mono

from pipelines.pipeline_acrcloud import run_acrcloud
from pipelines.pipeline_whisper_genius import run_whisper_genius
from pipelines.pipeline_custom import run_custom

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
        # Lato client, le card arriveranno in questo ordine dinamico
        tasks = [
            asyncio.create_task(run_acrcloud(audio_path)),
            asyncio.create_task(run_whisper_genius(audio_path)),
            asyncio.create_task(run_custom(audio_path)),
        ]
        done, pending = set(), set()

        # Opzionale: timeout globale (es. 45s)
        TIMEOUT = int(os.getenv("SSE_TIMEOUT_SEC", "45"))
        try:
            start = asyncio.get_event_loop().time()
            while tasks:
                # risveglia quando *un* task termina
                finished, tasks = await asyncio.wait(tasks, timeout=0.1, return_when=asyncio.FIRST_COMPLETED)
                for t in finished:
                    try:
                        payload = t.result()  # dict
                    except Exception as e:
                        payload = {"source": "internal", "ok": False, "error": str(e)}

                    # invia un evento con il nome della pipeline come 'event'
                    yield sse_pack(event=payload.get("source", "unknown"), data=payload)
                # timeout hard
                if asyncio.get_event_loop().time() - start > TIMEOUT:
                    for t in tasks:
                        t.cancel()
                    yield sse_pack(event="timeout", data={"ok": False, "error": "timeout"})
                    break

            # evento finale
            yield sse_pack(event="done", data={"ok": True})
        except asyncio.CancelledError:
            # client ha chiuso
            pass
        except Exception as e:
            yield sse_pack(event="internal_error", data={"ok": False, "error": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# --- Fallback non-SSE: restituisce tutto insieme (sincrono) ---
@router.post("/identify_all")
async def identify_all(token: Optional[str] = None):
    """
    Non streaming: invoca in sequenza e ritorna un JSON unico.
    Utile per debug o client senza SSE.
    """
    if not token or token not in UPLOADS:
        raise HTTPException(status_code=400, detail="Token non valido")
    audio_path = UPLOADS[token]

    # esecuzione in parallelo ma attesa di tutti
    results = await asyncio.gather(
        run_acrcloud(audio_path),
        run_whisper_genius(audio_path),
        run_custom(audio_path),
        return_exceptions=True
    )
    out = []
    for r in results:
        if isinstance(r, Exception):
            out.append({"source": "internal", "ok": False, "error": str(r)})
        else:
            out.append(r)
    return {"ok": True, "results": out}