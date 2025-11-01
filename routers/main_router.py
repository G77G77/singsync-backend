from fastapi import APIRouter, UploadFile, File
import asyncio, uuid, os, tempfile
from pipelines.pipeline_acrcloud import run_acrcloud
from pipelines.pipeline_whisper_genius import run_whisper_genius
from pipelines.pipeline_custom import run_custom
from pipelines.pipeline_genius_text import run_genius_text

router = APIRouter()

ENABLE_ACRCLOUD = os.getenv("ENABLE_ACRCLOUD", "1") == "1"
ENABLE_WHISPER_GENIUS = os.getenv("ENABLE_WHISPER_GENIUS", "1") == "1"
ENABLE_CUSTOM = os.getenv("ENABLE_CUSTOM", "0") == "1"

TOKENS = {}

@router.post("/upload_audio")
async def upload_audio(file: UploadFile = File(...)):
    token = str(uuid.uuid4())[:8]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    TOKENS[token] = tmp_path
    return {"ok": True, "token": token}

@router.get("/identify_all")
async def identify_all(token: str):
    if token not in TOKENS:
        return {"ok": False, "error": "invalid_token"}

    path = TOKENS[token]
    results = []

    tasks = []
    if ENABLE_ACRCLOUD:
        tasks.append(run_acrcloud(path))
    else:
        results.append({"source": "acrcloud", "ok": False, "disabled": True, "elapsed_sec": 0})

    if ENABLE_WHISPER_GENIUS:
        tasks.append(run_whisper_genius(path))
    else:
        results.append({"source": "whisper_genius", "ok": False, "disabled": True, "elapsed_sec": 0})

    if ENABLE_CUSTOM:
        tasks.append(run_custom(path))
    else:
        results.append({"source": "custom", "ok": False, "disabled": True, "elapsed_sec": 0})

    try:
        more = await asyncio.gather(*tasks)
        results.extend(more)
        return {"ok": True, "results": results}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/identify_text")
async def identify_text(query: str):
    """Ricerca testuale su Genius"""
    return await run_genius_text(query)