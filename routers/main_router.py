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

UPLOADS: Dict[str, str] = {}


# --- UPLOAD AUDIO ---
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


# --- SSE PIPELINE AUDIO ---
@router.get("/identify_stream")
async def identify_stream(token: str = Query(...)):
    if token not in UPLOADS:
        raise HTTPException(status_code=400, detail="Token non valido")
    audio_path = UPLOADS[token]

    async def event_generator():
        tasks = []
        if os.getenv("ENABLE_ACRCLOUD", "1") == "1":
            tasks.append(asyncio.create_task(run_acrcloud(audio_path)))
        if os.getenv("ENABLE_WHISPER_GENIUS", "1") == "1":
            tasks.append(asyncio.create_task(run_whisper_genius(audio_path)))
        if os.getenv("ENABLE_CUSTOM", "0") == "1":
            tasks.append(asyncio.create_task(run_custom(audio_path)))

        TIMEOUT = int(os.getenv("SSE_TIMEOUT_SEC", "45"))
        try:
            start = asyncio.get_event_loop().time()
            while tasks:
                finished, tasks = await asyncio.wait(tasks, timeout=0.1, return_when=asyncio.FIRST_COMPLETED)
                for t in finished:
                    try:
                        payload = t.result()
                    except Exception as e:
                        payload = {"source": "internal", "ok": False, "error": str(e)}

                    yield sse_pack(event=payload.get("source", "unknown"), data=payload)

                if asyncio.get_event_loop().time() - start > TIMEOUT:
                    for t in tasks:
                        t.cancel()
                    yield sse_pack(event="timeout", data={"ok": False, "error": "timeout"})
                    break

            yield sse_pack(event="done", data={"ok": True})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            yield sse_pack(event="internal_error", data={"ok": False, "error": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# --- RICERCA TESTUALE SU GENIUS ---
@router.get("/identify_text")
async def identify_text(query: str):
    """
    Ricerca su Genius usando testo libero (titolo/artista).
    """
    try:
        from utils.genius_search import search_genius_text
        results = await search_genius_text(query)
        return {"ok": True, "results": results}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# --- FALLBACK NON-SSE ---
@router.post("/identify_all")
async def identify_all(token: Optional[str] = None):
    if not token or token not in UPLOADS:
        raise HTTPException(status_code=400, detail="Token non valido")
    audio_path = UPLOADS[token]

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