from fastapi import FastAPI, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel
from pydub import AudioSegment
import requests, os, tempfile, traceback, uvicorn

app = FastAPI(title="SingSync Backend", version="2.3")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Inizializza Whisper ---
print("🚀 Caricamento modello Whisper (distil-large-v3)...")
model = WhisperModel("distil-large-v3", device="cpu")
print("✅ Modello Whisper caricato.")

# --- Chiavi API ---
AUDD_API_TOKEN = os.getenv("AUDD_API_TOKEN")
GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN")

@app.get("/health")
def health():
    """Verifica stato del backend"""
    return {"status": "ok", "message": "Backend SingSync attivo e funzionante!"}


# --- Conversione MP3 ---
def convert_to_mp3(input_path):
    """Converte l'audio in MP3 per AudD"""
    try:
        audio = AudioSegment.from_file(input_path)
        out_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        audio.export(out_path, format="mp3")
        print(f"🎧 File convertito in MP3: {out_path}")
        return out_path
    except Exception as e:
        print(f"⚠️ Errore conversione MP3: {e}")
        return input_path


# --- Trascrizione audio ---
@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile):
    """Endpoint per trascrivere l'audio con Whisper"""
    try:
        tmp = f"/tmp/{audio.filename}"
        with open(tmp, "wb") as f:
            f.write(await audio.read())

        segs, info = model.transcribe(tmp)
        text = " ".join([s.text for s in segs])
        print(f"✅ Trascrizione: {text[:120]}...")
        return {"transcript": text}

    except Exception as e:
        print("❌ Errore trascrizione:", e)
        traceback.print_exc()
        return {"error": str(e)}


# --- Identificazione canzone ---
@app.post("/identify")
async def identify(audio: UploadFile = None, text: str = Form(None)):
    """Endpoint principale: combina Whisper, Genius e AudD"""
    try:
        results = []
        whisper_text = text
        audio_path = None

        # 1️⃣ Se arriva un file → trascrivi
        if audio:
            audio_path = f"/tmp/{audio.filename}"
            with open(audio_path, "wb") as f:
                f.write(await audio.read())

            segs, info = model.transcribe(audio_path)
            whisper_text = " ".join([s.text for s in segs])
            print(f"🎙️ Whisper → {whisper_text[:120]}...")

        # 2️⃣ Genius
        genius_results = []
        if whisper_text and GENIUS_API_TOKEN:
            try:
                headers = {"Authorization": f"Bearer {GENIUS_API_TOKEN}"}
                r = requests.get(
                    "https://api.genius.com/search",
                    headers=headers,
                    params={"q": whisper_text},
                )
                data = r.json()
                for hit in data.get("response", {}).get("hits", []):
                    song = hit["result"]
                    genius_results.append({
                        "id": song["id"],
                        "title": song["title"],
                        "artist": song["primary_artist"]["name"],
                        "url": song["url"],
                        "confidence": 0.5,
                        "source": "whisper+genius"
                    })
            except Exception as e:
                print(f"⚠️ Errore Genius: {e}")

        # 3️⃣ AudD (in parallelo)
        audd_results = []
        if AUDD_API_TOKEN:
            print("🎵 Avvio chiamata AudD...")
            try:
                data = {"api_token": AUDD_API_TOKEN, "return": "timecode,spotify"}

                if audio_path and os.path.exists(audio_path):
                    mp3_path = convert_to_mp3(audio_path)
                    with open(mp3_path, "rb") as f:
                        r = requests.post("https://api.audd.io/", data=data, files={"file": f})
                else:
                    # anche solo testo
                    data["q"] = whisper_text or text or ""
                    r = requests.post("https://api.audd.io/findLyrics/", data=data)

                print(f"📡 Risposta grezza AudD: {r.text[:400]}")
                res_json = r.json()

                if "result" in res_json and res_json["result"]:
                    for s in res_json["result"][:3]:
                        audd_results.append({
                            "title": s.get("title", "Sconosciuto"),
                            "artist": s.get("artist", "Sconosciuto"),
                            "url": s.get("song_link") or s.get("spotify", {}).get("external_urls", {}).get("spotify", ""),
                            "confidence": 0.7,
                            "source": "audd"
                        })
            except Exception as e:
                print(f"⚠️ Errore chiamata AudD: {e}")
        else:
            print("⚙️ AudD non inizializzato: nessuna chiave trovata")

        # 4️⃣ Fusione risultati
        merged = genius_results.copy()
        for ar in audd_results:
            found = False
            for gr in merged:
                if ar["title"].lower() == gr["title"].lower():
                    gr["confidence"] = max(gr["confidence"], ar["confidence"])
                    gr["source"] = "whisper+audd+genius"
                    found = True
                    break
            if not found:
                merged.append(ar)

        if not merged:
            return {"results": [], "message": "Nessuna canzone trovata."}

        print(f"✅ Restituiti {len(merged)} risultati totali.")
        return {"query": whisper_text, "results": merged}

    except Exception as e:
        print("❌ Errore identify:", e)
        traceback.print_exc()
        return {"error": str(e)}


# --- Avvio manuale per Railway (porta dinamica) ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
