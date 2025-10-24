import os
import io
import json
import time
import uuid
import asyncio
import tempfile
import traceback
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import requests

from audio_features import extract_features


# ===========================
# ⚙️ CONFIGURAZIONE FASTAPI
# ===========================
app = FastAPI(title="SingSync Backend", version="4.0-streaming")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: limitare al dominio della tua app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================
# 🔑 VARIABILI D’AMBIENTE
# ===========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN")
AUDD_API_TOKEN = os.getenv("AUDD_API_TOKEN")
ARCCLOUD_ACCESS_KEY = os.getenv("ARCCLOUD_ACCESS_KEY")
ARCCLOUD_ACCESS_SECRET = os.getenv("ARCCLOUD_ACCESS_SECRET")
ARCCLOUD_HOST = os.getenv("ARCCLOUD_HOST", "identify-eu-west-1.acrcloud.com")


TMP_DIR = "/tmp/singsync_uploads"
os.makedirs(TMP_DIR, exist_ok=True)
UPLOADS: Dict[str, str] = {}  # token → file path


# ===========================
# 💚 HEALTHCHECK
# ===========================
@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "SingSync Backend",
        "env": {
            "OPENAI_API_KEY": bool(OPENAI_API_KEY),
            "GENIUS_API_TOKEN": bool(GENIUS_API_TOKEN),
            "AUDD_API_TOKEN": bool(AUDD_API_TOKEN),
            "ARCCLOUD_ACCESS_KEY": bool(ARCCLOUD_ACCESS_KEY),
        },
    }


# ===========================
# 🎧 UPLOAD AUDIO
# ===========================
@app.post("/upload_audio")
async def upload_audio(audio: UploadFile = File(...)):
    try:
        token = str(uuid.uuid4())[:12]
        tmp_path = os.path.join(TMP_DIR, f"{token}.wav")
        with open(tmp_path, "wb") as f:
            f.write(await audio.read())

        UPLOADS[token] = tmp_path
        print(f"📥 Upload ricevuto, token={token}, path={tmp_path}")
        return {"ok": True, "token": token}
    except Exception as e:
        print("❌ Errore upload_audio:", e)
        traceback.print_exc()
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ===========================
# 🧠 FUNZIONI UTILI
# ===========================
def openai_transcribe_wav(path: str) -> str:
    """Usa Whisper (OpenAI API) per trascrivere WAV."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY mancante")
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    with open(path, "rb") as f:
        files = {"file": (os.path.basename(path), f, "audio/wav")}
        data = {"model": "whisper-1"}
        r = requests.post(url, headers=headers, files=files, data=data, timeout=120)
    jr = r.json()
    if "error" in jr:
        raise RuntimeError(f"Whisper API error: {jr['error']}")
    return jr.get("text", "").strip()


def genius_search(q: str) -> List[Dict[str, Any]]:
    """Cerca su Genius tramite testo."""
    if not q or not GENIUS_API_TOKEN:
        return []
    try:
        headers = {"Authorization": f"Bearer {GENIUS_API_TOKEN}"}
        r = requests.get("https://api.genius.com/search", headers=headers, params={"q": q})
        hits = r.json().get("response", {}).get("hits", [])
        return [
            {
                "title": h["result"]["title"],
                "artist": h["result"]["primary_artist"]["name"],
                "url": h["result"]["url"],
                "source": "whisper+genius",
                "confidence": 0.5,
            }
            for h in hits
        ]
    except Exception as e:
        print("⚠️ Genius error:", e)
        return []


def arccloud_identify(path: str) -> List[Dict[str, Any]]:
    """Identifica tramite ARCCloud (fingerprint)."""
    if not ARCCLOUD_ACCESS_KEY or not ARCCLOUD_ACCESS_SECRET:
        return []
    try:
        with open(path, "rb") as f:
            files = {"sample": f}
            data = {
                "access_key": ARCCLOUD_ACCESS_KEY,
                "data_type": "audio",
                "sample_bytes": os.path.getsize(path),
            }
            r = requests.post(f"https://{ARCCLOUD_HOST}/v1/identify", data=data, files=files, timeout=60)
            jr = r.json()
            if jr.get("status", {}).get("code") == 0:
                music = jr.get("metadata", {}).get("music", [])
                out = []
                for m in music[:3]:
                    out.append({
                        "title": m.get("title"),
                        "artist": ", ".join(a["name"] for a in m.get("artists", [])),
                        "album": (m.get("album") or {}).get("name"),
                        "confidence": 0.9,
                        "source": "arccloud",
                    })
                return out
    except Exception as e:
        print("⚠️ ARCCloud error:", e)
    return []


def features_extract(path: str) -> Dict[str, Any]:
    """Estrae feature con Librosa+CREPE."""
    try:
        return extract_features(path)
    except Exception as e:
        print("⚠️ Feature extraction error:", e)
        return {"error": str(e)}


# ===========================
# 🚀 STREAMING IDENTIFY (SSE)
# ===========================
@app.get("/identify_stream")
async def identify_stream(token: str):
    """Invia in streaming (SSE) i risultati dei 3 metodi."""

    async def event_gen():
        try:
            # 👇 YIELD iniziale per sbloccare connessione
            yield {"event": "message", "data": {"status": "started"}}
            print("🔄 SSE avviato, in attesa risultati...")

            if token not in UPLOADS:
                yield {"event": "error", "data": {"message": "token non valido"}}
                return

            file_path = UPLOADS[token]
            print(f"🎧 Avvio elaborazione file: {file_path}")

            # ---- 1️⃣ ARCCloud ----
            start = time.time()
            arc_res = await asyncio.to_thread(arccloud_identify, file_path)
            yield {"event": "message", "data": {"source": "arccloud", "results": arc_res}}
            print(f"📤 ARCCloud completato in {time.time()-start:.1f}s")

            # ---- 2️⃣ Whisper + Genius ----
            start = time.time()
            try:
                text = await asyncio.to_thread(openai_transcribe_wav, file_path)
                g_res = await asyncio.to_thread(genius_search, text)
            except Exception as e:
                g_res = [{"error": str(e)}]
            yield {"event": "message", "data": {"source": "whisper_genius", "results": g_res}}
            print(f"📤 Whisper+Genius completato in {time.time()-start:.1f}s")

            # ---- 3️⃣ Features (Librosa+CREPE) ----
            start = time.time()
            feats = await asyncio.to_thread(features_extract, file_path)
            yield {"event": "message", "data": {"source": "features", "results": feats}}
            print(f"📤 Features completato in {time.time()-start:.1f}s")

            yield {"event": "message", "data": {"status": "done"}}
            print("✅ SSE completato per token", token)

        except Exception as e:
            print("❌ Errore SSE:", e)
            traceback.print_exc()
            yield {"event": "error", "data": {"message": str(e)}}

    async def stream():
        async for ev in event_gen():
            yield f"data: {json.dumps(ev['data'])}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ===========================
# 🧩 IDENTIFY SYNC (fallback, tutto in una volta)
# ===========================
@app.post("/identify_multi")
async def identify_multi(audio: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(await audio.read())
            wav_path = tmp.name

        arc = arccloud_identify(wav_path)
        text = openai_transcribe_wav(wav_path)
        genius = genius_search(text)
        feats = features_extract(wav_path)

        return {
            "arccloud": arc,
            "whisper_genius": genius,
            "features": feats,
        }
    except Exception as e:
        print("❌ Errore identify_multi:", e)
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=200)
