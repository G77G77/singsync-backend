import os, io, tempfile, traceback
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests

from audio_features import extract_features

# ------------------------------
# Config FastAPI + CORS
# ------------------------------
app = FastAPI(title="SingSync Backend", version="3.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # restringi in futuro (es. il tuo dominio/app)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# Env keys
# ------------------------------
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
GENIUS_API_TOKEN  = os.getenv("GENIUS_API_TOKEN")
AUDD_API_TOKEN    = os.getenv("AUDD_API_TOKEN")

# ------------------------------
# Health
# ------------------------------
@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "SingSync Backend",
        "whisper_api": bool(OPENAI_API_KEY),
        "genius": bool(GENIUS_API_TOKEN),
        "audd": bool(AUDD_API_TOKEN),
        "features": True
    }

# ------------------------------
# Helpers
# ------------------------------
def openai_transcribe_wav(path: str) -> str:
    """
    Usa OpenAI Whisper API (gpt-4o-mini-transcribe) per trascrivere WAV/PCM.
    Ritorna stringa testo (anche vuota) oppure solleva eccezione.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY non configurata")

    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    with open(path, "rb") as f:
        files = {
            "file": (os.path.basename(path), f, "audio/wav"),
        }
        data = {
            "model": "gpt-4o-mini-transcribe",
            "language": "auto",          # autodetect
            # "response_format": "json", # default json
        }
        r = requests.post(url, headers=headers, data=data, files=files, timeout=60)
    # Può tornare sia JSON con "text" sia error
    try:
        jr = r.json()
    except Exception:
        raise RuntimeError(f"Whisper API response non-JSON: {r.text[:200]}")
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

def audd_recognize(file_path: Optional[str], q_text: Optional[str]) -> List[Dict[str, Any]]:
    out = []
    if not AUDD_API_TOKEN:
        return out
    try:
        base_data = {"api_token": AUDD_API_TOKEN, "return": "timecode,spotify"}
        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                r = requests.post("https://api.audd.io/", data=base_data, files={"file": f}, timeout=60)
        else:
            # fallback testo (trova per lyrics)
            data = dict(base_data)
            data["q"] = q_text or ""
            r = requests.post("https://api.audd.io/findLyrics/", data=data, timeout=30)

        jr = r.json()
        res = jr.get("result")
        if isinstance(res, dict):
            # formato riconoscimento singolo
            title = res.get("title")
            artist = res.get("artist")
            url = res.get("song_link") or (res.get("spotify") or {}).get("external_urls", {}).get("spotify", "")
            preview = (res.get("spotify") or {}).get("preview_url")
            image = (res.get("spotify") or {}).get("album", {}).get("images", [{}])[0].get("url")
            out.append({
                "title": title, "artist": artist, "url": url,
                "preview": preview, "image": image,
                "source": "audd", "confidence": 0.7
            })
        elif isinstance(res, list):
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
                # arricchisci con preview/cover se mancanti
                if not gr.get("preview") and ar.get("preview"):
                    gr["preview"] = ar["preview"]
                if not gr.get("image") and ar.get("image"):
                    gr["image"] = ar["image"]
                found = True
                break
        if not found:
            merged.append(ar)
    # Ordina per confidenza desc
    merged.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return merged

# ------------------------------
# Endpoint: TRASCRIZIONE (OpenAI Whisper API)
# ------------------------------
@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """
    Attende un file WAV/PCM dal frontend. Ritorna {"transcript": "..."}.
    """
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(await audio.read())
            wav_path = tmp.name

        text = openai_transcribe_wav(wav_path)
        return {"transcript": text}
    except Exception as e:
        print("❌ Errore Whisper:", e)
        return JSONResponse({"error": str(e)}, status_code=200)

# ------------------------------
# Endpoint: IDENTIFY (parallelo Whisper+Genius e AudD)
# - Se arriva un file audio usa Whisper API per fare testo + Genius
# - In parallelo chiama AudD su file (se presente) o su testo
# ------------------------------
@app.post("/identify")
async def identify(audio: UploadFile = None, text: str = Form(None)):
    try:
        wav_path = None
        whisper_text = text.strip() if text else ""

        if audio:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(await audio.read())
                wav_path = tmp.name

            # trascrizione via API
            try:
                whisper_text = openai_transcribe_wav(wav_path)
                print("📝 Whisper:", whisper_text[:120])
            except Exception as e:
                print("⚠️ Whisper fallita:", e)

        # Query testuale (se c'è)
        genius_res = genius_search(whisper_text)

        # AudD in parallelo (file se c'è, altrimenti testo)
        audd_res = audd_recognize(wav_path, whisper_text or text)

        # Merge + ranking
        merged = merge_results(genius_res, audd_res)

        return {"query": whisper_text or text or "", "results": merged}

    except Exception as e:
        print("❌ Errore identify:", e)
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=200)

# ------------------------------
# Endpoint: FEATURES (Fase 1 – Feature Extraction)
# Accetta WAV, estrae feature musicali CPU-only (librosa + YIN).
# ------------------------------
@app.post("/features")
async def features(audio: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(await audio.read())
            wav_path = tmp.name

        feats = extract_features(wav_path)
        return {"features": feats}
    except Exception as e:
        print("❌ Errore features:", e)
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=200)