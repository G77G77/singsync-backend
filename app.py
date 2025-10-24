import os
import io
import json
import hmac
import base64
import time
import hashlib
import asyncio
import tempfile
from typing import Optional, List, Dict, Any

import requests
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from audio_features import extract_features  # Fase 1 feature extraction

app = FastAPI(title="SingSync Backend", version="4.0 - MultiChannel Test Mode")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === ENV KEYS ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN")
ARCCLOUD_HOST = os.getenv("ARCCLOUD_HOST")
ARCCLOUD_ACCESS_KEY = os.getenv("ARCCLOUD_ACCESS_KEY")
ARCCLOUD_ACCESS_SECRET = os.getenv("ARCCLOUD_ACCESS_SECRET")

# === LOG FILE ===
LOG_DIR = "/tmp/logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "identify_debug.jsonl")

def log_jsonl(payload: Dict[str, Any]):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as e:
        print("⚠️ Log write error:", e)

# === HELPERS ===
def now_ms():
    return int(time.time() * 1000)

# --- Whisper API ---
def openai_transcribe_wav(path: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY non configurata")

    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    with open(path, "rb") as f:
        files = {"file": (os.path.basename(path), f, "audio/wav")}
        data = {"model": "whisper-1"}
        r = requests.post(url, headers=headers, data=data, files=files, timeout=60)
    jr = r.json()
    if "error" in jr:
        raise RuntimeError(f"Whisper API error: {jr['error']}")
    return jr.get("text", "").strip()

# --- Genius ---
def genius_search(q: str):
    out = []
    if not GENIUS_API_TOKEN or not q:
        return out
    try:
        headers = {"Authorization": f"Bearer {GENIUS_API_TOKEN}"}
        resp = requests.get("https://api.genius.com/search",
                            headers=headers, params={"q": q}, timeout=15)
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

# --- ARCCloud ---
def _arc_sign(secret: str, msg: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha1)
    return base64.b64encode(mac.digest()).decode("utf-8")

def arccloud_identify(file_path: str) -> Dict[str, Any]:
    t0 = time.perf_counter()
    if not (ARCCLOUD_HOST and ARCCLOUD_ACCESS_KEY and ARCCLOUD_ACCESS_SECRET):
        return {"status": "skipped", "reason": "ARCCloud non configurato", "matches": []}

    endpoint = f"https://{ARCCLOUD_HOST}/v1/identify"
    ts = str(int(time.time()))
    sign_str = "\n".join(["POST", "/v1/identify", ARCCLOUD_ACCESS_KEY, "audio", "1", ts])
    signature = _arc_sign(ARCCLOUD_ACCESS_SECRET, sign_str)

    data = {
        "access_key": ARCCLOUD_ACCESS_KEY,
        "sample_bytes": os.path.getsize(file_path),
        "timestamp": ts,
        "signature": signature,
        "data_type": "audio",
        "signature_version": "1",
    }

    try:
        with open(file_path, "rb") as f:
            r = requests.post(endpoint, data=data, files={"sample": f}, timeout=30)
        jr = r.json()
        music = (jr.get("metadata") or {}).get("music") or []
        results = []
        for m in music[:5]:
            title = m.get("title")
            artist = (m.get("artists") or [{}])[0].get("name")
            results.append({
                "title": title,
                "artist": artist,
                "source": "arccloud",
                "confidence": m.get("score", 0)
            })
        latency = round(time.perf_counter() - t0, 3)
        return {"status": "ok", "latency": latency, "matches": results}
    except Exception as e:
        return {"status": "error", "reason": str(e)}

# --- Whisper + Genius ---
def whisper_plus_genius(file_path: Optional[str], text: Optional[str]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    try:
        transcript = openai_transcribe_wav(file_path) if file_path else (text or "")
        matches = genius_search(transcript)
        latency = round(time.perf_counter() - t0, 3)
        return {"status": "ok", "latency": latency, "transcript": transcript, "matches": matches}
    except Exception as e:
        return {"status": "error", "reason": str(e)}

# --- Librosa + CREPE ---
def librosa_crepe_block(file_path: str) -> Dict[str, Any]:
    t0 = time.perf_counter()
    try:
        feats = extract_features(file_path)
        try:
            import crepe  # noqa
            feats["crepe_used"] = True
            status = "ok"
        except Exception:
            feats["crepe_used"] = False
            status = "partial"
        latency = round(time.perf_counter() - t0, 3)
        return {"status": status, "latency": latency, "features": feats}
    except Exception as e:
        return {"status": "error", "reason": str(e)}

# --- Health check ---
@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "SingSync Backend",
        "whisper": bool(OPENAI_API_KEY),
        "genius": bool(GENIUS_API_TOKEN),
        "arccloud": all([ARCCLOUD_HOST, ARCCLOUD_ACCESS_KEY, ARCCLOUD_ACCESS_SECRET]),
        "features": True,
    }

# --- Identify Multi ---
@app.post("/identify_multi")
async def identify_multi(audio: UploadFile = File(...), text: str = Form(None)):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(await audio.read())
        wav_path = tmp.name

    start = now_ms()
    arc_task = asyncio.to_thread(arccloud_identify, wav_path)
    wg_task = asyncio.to_thread(whisper_plus_genius, wav_path, text)
    feats_task = asyncio.to_thread(librosa_crepe_block, wav_path)
    arc, wg, feats = await asyncio.gather(arc_task, wg_task, feats_task)

    result = {"ARCCloud": arc, "Whisper_Genius": wg, "Librosa_CREPE": feats}
    log_jsonl({"ts": start, "results": result})

    return {"query_id": start, "input_file": os.path.basename(wav_path), "results": result}
