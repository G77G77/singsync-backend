from fastapi import FastAPI, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydub import AudioSegment
import requests, os, tempfile, traceback

app = FastAPI(title="SingSync Backend", version="3.0")

# --- CORS (per frontend mobile) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Chiavi API ---
AUDD_API_TOKEN = os.getenv("AUDD_API_TOKEN")
GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

@app.get("/health")
def health():
    return {"status": "ok", "message": "Backend SingSync attivo e funzionante!"}

# --- Funzione di conversione MP3 ---
def convert_to_mp3(input_path):
    try:
        audio = AudioSegment.from_file(input_path)
        out_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        audio.export(out_path, format="mp3")
        print(f"🎧 File convertito in MP3: {out_path}")
        return out_path
    except Exception as e:
        print(f"⚠️ Errore conversione MP3: {e}")
        return input_path

# --- TRASCRIZIONE con OpenAI Whisper API ---
@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile):
    try:
        tmp = f"/tmp/{audio.filename}"
        with open(tmp, "wb") as f:
            f.write(await audio.read())

        # Conversione in MP3 (più stabile)
        mp3_path = convert_to_mp3(tmp)

        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        with open(mp3_path, "rb") as f:
            response = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                files={"file": (audio.filename, f, "audio/mpeg")},
                data={"model": "whisper-1"},
            )

        if response.status_code != 200:
            print("❌ Errore Whisper:", response.text)
            return {"error": f"Errore Whisper: {response.text}"}

        transcript = response.json().get("text", "")
        print(f"✅ Trascrizione: {transcript[:120]}...")
        return {"transcript": transcript}

    except Exception as e:
        print("❌ Errore transcribe:", e)
        traceback.print_exc()
        return {"error": str(e)}

# --- IDENTIFICAZIONE CANZONE ---
@app.post("/identify")
async def identify(audio: UploadFile = None, text: str = Form(None)):
    try:
        results = []
        whisper_text = text
        audio_path = None

        # 1️⃣ Se arriva un file, usa Whisper API
        if audio:
            audio_path = f"/tmp/{audio.filename}"
            with open(audio_path, "wb") as f:
                f.write(await audio.read())

            mp3_path = convert_to_mp3(audio_path)

            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
            with open(mp3_path, "rb") as f:
                response = requests.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers=headers,
                    files={"file": (audio.filename, f, "audio/mpeg")},
                    data={"model": "whisper-1"},
                )
            whisper_text = response.json().get("text", "")
            print(f"🎙️ Whisper → {whisper_text[:120]}...")

        # 2️⃣ Genius
        genius_results = []
        if whisper_text and GENIUS_API_TOKEN:
            try:
                headers = {"Authorization": f"Bearer {GENIUS_API_TOKEN}"}
                r = requests.get("https://api.genius.com/search",
                                 headers=headers, params={"q": whisper_text})
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

        # 3️⃣ AudD (parallel fallback)
        audd_results = []
        if AUDD_API_TOKEN:
            print("🎵 Avvio chiamata AudD...")
            try:
                data = {"api_token": AUDD_API_TOKEN, "return": "spotify,timecode"}
                if audio_path and os.path.exists(audio_path):
                    mp3_path = convert_to_mp3(audio_path)
                    with open(mp3_path, "rb") as f:
                        r = requests.post("https://api.audd.io/", data=data, files={"file": f})
                else:
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
