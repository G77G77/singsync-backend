import os, io, uuid, asyncio, tempfile, traceback
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse
import requests

from audio_features import extract_features  # già presente nel tuo repo

# =========================
# Config FastAPI + CORS
# =========================
app = FastAPI(title="SingSync Backend", version="3.2-stream")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # restringi in futuro
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
GENIUS_API_TOKEN  = os.getenv("GENIUS_API_TOKEN")
AUDD_API_TOKEN    = os.getenv("AUDD_API_TOKEN")
ARCCLOUD_HOST     = os.getenv("ARCCLOUD_HOST")
ARCCLOUD_ACCESS_KEY    = os.getenv("ARCCLOUD_ACCESS_KEY")
ARCCLOUD_ACCESS_SECRET = os.getenv("ARCCLOUD_ACCESS_SECRET")

# In-memory “upload cache” (solo per test su istanza singola)
UPLOAD_CACHE: Dict[str, str] = {}

@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "SingSync Backend (SSE)",
        "whisper_api": bool(OPENAI_API_KEY),
        "genius": bool(GENIUS_API_TOKEN),
        "audd": bool(AUDD_API_TOKEN),
        "arccloud": bool(ARCCLOUD_ACCESS_KEY and ARCCLOUD_ACCESS_SECRET and ARCCLOUD_HOST),
        "features": True
    }

# =========================
# Helpers
# =========================
def openai_transcribe_wav(path: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY non configurata")

    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    with open(path, "rb") as f:
        files = { "file": (os.path.basename(path), f, "audio/wav") }
        data = { "model": "whisper-1", "language": "auto" }
        r = requests.post(url, headers=headers, data=data, files=files, timeout=120)
    jr = r.json()
    if "error" in jr:
        raise RuntimeError(f"Whisper API error: {jr['error']}")
    return jr.get("text", "").strip()

def genius_search(q: str) -> List[Dict[str, Any]]:
    out = []
    if not GENIUS_API_TOKEN or not q:
        return out
    try:
        headers = {"Authorization": f"Bearer {GENIUS_API_TOKEN}"}
        resp = requests.get("https://api.genius.com/search",
                            headers=headers, params={"q": q}, timeout=20)
        data = resp.json()
        for hit in data.get("response", {}).get("hits", []):
            s = hit["result"]
            out.append({
                "id": s.get("id"),
                "title": s.get("title"),
                "artist": s.get("primary_artist", {}).get("name"),
                "url": s.get("url"),
                "source": "whisper+genius",
                "confidence": 0.5
            })
    except Exception as e:
        print("⚠️ Errore Genius:", e)
    return out

def audd_recognize(file_path: Optional[str], q_text: Optional[str]) -> List[Dict[str, Any]]:
    out = []
    if not AUDD_API_TOKEN:
        return out
    try:
        base_data = {"api_token": AUDD_API_TOKEN, "return": "timecode,spotify"}
        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                r = requests.post("https://api.audd.io/", data=base_data, files={"file": f}, timeout=120)
        else:
            data = dict(base_data)
            data["q"] = q_text or ""
            r = requests.post("https://api.audd.io/findLyrics/", data=data, timeout=60)

        jr = r.json()
        res = jr.get("result")
        # normalizza singolo / lista
        if isinstance(res, dict):
            res = [res]
        if isinstance(res, list):
            for s in res[:5]:
                title = s.get("title") or s.get("song_title")
                artist = s.get("artist") or s.get("artist_name")
                url = s.get("song_link") or (s.get("spotify") or {}).get("external_urls", {}).get("spotify", "")
                preview = (s.get("spotify") or {}).get("preview_url")
                image = (s.get("spotify") or {}).get("album", {}).get("images", [{}])[0].get("url")
                out.append({
                    "title": title, "artist": artist, "url": url,
                    "preview": preview, "image": image,
                    "source": "audd", "confidence": 0.7
                })
    except Exception as e:
        print("⚠️ Errore AudD:", e)
    return out

def arccloud_recognize(file_path: str) -> List[Dict[str, Any]]:
    """
    Esempio minimo ACRCloud; richiede set di ARCCLOUD_*.
    Puoi sostituire con la tua implementazione attuale.
    Per demo, se non configurato ritorna [].
    """
    if not (ARCCLOUD_ACCESS_KEY and ARCCLOUD_ACCESS_SECRET and ARCCLOUD_HOST):
        return []
    try:
        # Qui va la firma HMAC di ACRCloud (omessa per brevità)
        # Per i test, facciamo finta che non sia disponibile → return []
        return []
    except Exception as e:
        print("⚠️ Errore ACRCloud:", e)
        return []

def merge_results(genius_res: List[Dict[str, Any]], audd_res: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged = genius_res[:]
    for ar in audd_res:
        found = False
        for gr in merged:
            if not gr.get("title") or not gr.get("artist"):
                continue
            if not ar.get("title") or not ar.get("artist"):
                continue
            if ar["title"].lower() == gr["title"].lower() and ar["artist"].lower() == gr["artist"].lower():
                gr["confidence"] = max(gr.get("confidence", 0.5), ar.get("confidence", 0.7))
                gr["source"] = "whisper+audd+genius"
                if not gr.get("preview") and ar.get("preview"):
                    gr["preview"] = ar["preview"]
                if not gr.get("image") and ar.get("image"):
                    gr["image"] = ar["image"]
                found = True
                break
        if not found:
            merged.append(ar)
    merged.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return merged

# =========================
# Upload step (SSE richiede GET, quindi separiamo upload e stream)
# =========================
@app.post("/upload_audio")
async def upload_audio(audio: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(await audio.read())
            wav_path = tmp.name
        token = uuid.uuid4().to_string() if hasattr(uuid.uuid4(), "to_string") else str(uuid.uuid4())
        UPLOAD_CACHE[token] = wav_path
        return {"ok": True, "token": token}
    except Exception as e:
        print("❌ Errore upload_audio:", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)

# =========================
# SSE: invia una card appena un motore termina
# =========================
@app.get("/identify_stream")
async def identify_stream(token: str = Query(...)):
    if token not in UPLOAD_CACHE:
        return JSONResponse({"error": "token non valido"}, status_code=400)

    wav_path = UPLOAD_CACHE[token]

    async def event_gen():
        try:
            async def _arc():
                res = await asyncio.to_thread(arccloud_recognize, wav_path)
                return {"source": "arccloud", "results": res}

            async def _whisper_genius():
                # whisper
                text = ""
                try:
                    text = await asyncio.to_thread(openai_transcribe_wav, wav_path)
                except Exception as e:
                    return {"source": "whisper_genius", "error": f"Whisper: {e}"}
                # genius
                gres = await asyncio.to_thread(genius_search, text)
                return {"source": "whisper_genius", "query": text, "results": gres}

            async def _features():
                feats = await asyncio.to_thread(extract_features, wav_path)
                return {"source": "features", "results": feats}

            tasks = [asyncio.create_task(_arc()),
                     asyncio.create_task(_whisper_genius()),
                     asyncio.create_task(_features())]

            for coro in asyncio.as_completed(tasks):
                chunk = await coro
                yield {"event": "message", "data": chunk}

        except asyncio.CancelledError:
            # client ha chiuso
            return
        except Exception as e:
            yield {"event": "message", "data": {"source":"internal","error": str(e)}}
        finally:
            # opzionale: cleanup file
            try:
                if os.path.exists(wav_path):
                    os.remove(wav_path)
            except:
                pass
            UPLOAD_CACHE.pop(token, None)
            yield {"event": "message", "data": {"status": "done"}}

    return EventSourceResponse(event_gen(), media_type="text/event-stream")

# =========================
# Endpoints legacy (restano per compatibilità)
# =========================
@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(await audio.read())
            wav_path = tmp.name
        text = openai_transcribe_wav(wav_path)
        return {"transcript": text}
    except Exception as e:
        print("❌ Errore Whisper:", e)
        return JSONResponse({"error": str(e)}, status_code=200)

@app.post("/identify")
async def identify(audio: UploadFile = None, text: str = Form(None)):
    try:
        wav_path = None
        whisper_text = text.strip() if text else ""

        if audio:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(await audio.read())
                wav_path = tmp.name
            try:
                whisper_text = openai_transcribe_wav(wav_path)
            except Exception as e:
                print("⚠️ Whisper fallita:", e)

        genius_res = genius_search(whisper_text)
        audd_res = audd_recognize(wav_path, whisper_text or text)
        merged = merge_results(genius_res, audd_res)
        return {"query": whisper_text or text or "", "results": merged}
    except Exception as e:
        print("❌ Errore identify:", e)
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=200)
