import os
import asyncio
import time
from fastapi import APIRouter, UploadFile, File, HTTPException
from utils.sse import sse_pack
from pipelines.pipeline_acrcloud import run_acrcloud
from pipelines.pipeline_whisper_genius import run_whisper_genius
from pipelines.pipeline_custom import run_custom
from pipelines.pipeline_genius_text import run_genius_text

router = APIRouter()
UPLOADS = {}

# =====================================================
# 🔹 Health Check
# =====================================================
@router.get("/health")
def health():
    return {"ok": True, "service": "SingSync backend active"}

# =====================================================
# 🔹 Upload file audio
# =====================================================
@router.post("/upload_audio")
async def upload_audio(file: UploadFile = File(...)):
    """Riceve un file audio e restituisce un token temporaneo."""
    try:
        token = str(int(time.time() * 1000))[-8:]
        save_path = f"/tmp/{token}.m4a"
        with open(save_path, "wb") as f:
            f.write(await file.read())
        UPLOADS[token] = save_path
        return {"ok": True, "token": token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# 🔹 Ricerca testuale su Genius
# =====================================================
@router.get("/identify_text")
async def identify_text(query: str):
    """Ricerca testuale su Genius."""
    return await run_genius_text(query)

# =====================================================
# 🔹 Identificazione completa (tutte le pipeline)
# =====================================================
@router.get("/identify_all")
async def identify_all(token: str):
    """Esegue tutte le pipeline (Whisper+Genius, ACRCloud, Custom)."""
    if token not in UPLOADS:
        raise HTTPException(status_code=400, detail="Token non valido")

    path = UPLOADS[token]
    tasks = []

    # ✅ ACRCloud (sincrono → wrapper async)
    if os.getenv("ENABLE_ACRCLOUD", "1") == "1":
        async def acr_wrapper():
            return await asyncio.to_thread(run_acrcloud, path)
        tasks.append(acr_wrapper())

    # ✅ Whisper + Genius (già async)
    if os.getenv("ENABLE_WHISPER_GENIUS", "1") == "1":
        tasks.append(run_whisper_genius(path))

    # ✅ Custom (sincrono → wrapper async)
    if os.getenv("ENABLE_CUSTOM", "0") == "1":
        async def custom_wrapper():
            return await asyncio.to_thread(run_custom, path)
        tasks.append(custom_wrapper())

    # 🔄 raccogli tutti i risultati
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

# =====================================================
# 🔹 Stream SSE (se usato)
# =====================================================
@router.get("/identify_stream")
async def identify_stream(token: str):
    """Versione streaming (per Expo fallback o SSE)."""
    if token not in UPLOADS:
        raise HTTPException(status_code=400, detail="Token non valido")

    path = UPLOADS[token]
    start = time.time()
    queue = asyncio.Queue()

    async def worker():
        try:
            for fn, enabled in [
                (run_acrcloud, os.getenv("ENABLE_ACRCLOUD", "1") == "1"),
                (run_whisper_genius, os.getenv("ENABLE_WHISPER_GENIUS", "1") == "1"),
                (run_custom, os.getenv("ENABLE_CUSTOM", "0") == "1"),
            ]:
                if not enabled:
                    await queue.put(sse_pack("message", {"source": fn.__name__, "ok": False, "disabled": True}))
                    continue

                if asyncio.iscoroutinefunction(fn):
                    res = await fn(path)
                else:
                    res = await asyncio.to_thread(fn, path)

                await queue.put(sse_pack("message", res))
            await queue.put(sse_pack("done", {"ok": True, "elapsed_sec": round(time.time() - start, 2)}))
        except Exception as e:
            await queue.put(sse_pack("error", {"error": str(e)}))

    asyncio.create_task(worker())

    async def event_generator():
        while True:
            data = await queue.get()
            yield data
            if "done" in data:
                break

    return EventSourceResponse(event_generator())