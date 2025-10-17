import os
import tempfile
import requests
from fastapi import FastAPI, UploadFile, File, Query
from faster_whisper import WhisperModel
from dotenv import load_dotenv

# carica le variabili dal file .env
load_dotenv()

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
GENIUS_TOKEN = os.getenv("GENIUS_TOKEN")

app = FastAPI(title="SingSync STT")

model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)


@app.get("/health")
def health():
    return {
        "ok": True,
        "model": WHISPER_MODEL,
        "device": WHISPER_DEVICE,
        "compute": WHISPER_COMPUTE,
        "genius_token_loaded": bool(GENIUS_TOKEN),
    }


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
        tmp.write(await audio.read())
        path = tmp.name

    segments, info = model.transcribe(
        path,
        language=None,
        beam_size=5,
        temperature=[0.0, 0.5, 1.0],
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300),
    )

    text = " ".join(s.text for s in segments).strip()
    lang = getattr(info, "language", "und")
    return {"language": lang, "transcript": text}


@app.get("/identify")
def identify(q: str = Query(..., description="Testo o frase per cercare la canzone")):
    """
    Riceve una query testuale e restituisce la lista di canzoni da Genius.
    """
    if not GENIUS_TOKEN:
        return {"error": "GENIUS_TOKEN mancante nel backend"}

    headers = {"Authorization": f"Bearer {GENIUS_TOKEN}"}
    url = "https://api.genius.com/search"
    params = {"q": q}

    try:
        print(f"\n🔎 Richiesta a Genius con query: {q}")
        r = requests.get(url, headers=headers, params=params, timeout=10)
        print(f"🔹 Status Genius API: {r.status_code}")

        if r.status_code != 200:
            return {"error": f"Genius API error {r.status_code}"}

        data = r.json()
        hits = data.get("response", {}).get("hits", [])
        print(f"📦 Numero risultati trovati: {len(hits)}")

        if not hits:
            print("⚠️ Nessun risultato da Genius")

        results = [
            {
                "id": h["result"]["id"],
                "title": h["result"]["title"],
                "artist": h["result"]["primary_artist"]["name"],
                "url": h["result"]["url"],
            }
            for h in hits
        ]
        print(f"✅ Risultati inviati al frontend: {len(results)}")
        return {"results": results}

    except Exception as e:
        print(f"❌ Errore nella richiesta a Genius: {e}")
        return {"error": str(e)}