# pipelines/pipeline_whisper_genius.py
import os
import traceback
import requests
import tempfile
import openai

# -------------------------------------------------------------
# Funzione principale della pipeline: Whisper + Genius
# -------------------------------------------------------------
async def run_whisper_genius(audio_path: str) -> dict:
    """
    Pipeline 2️⃣: trascrive un file audio tramite OpenAI Whisper API
    e cerca la canzone corrispondente tramite Genius API.

    Restituisce un dizionario pronto per essere inviato via SSE.
    """
    try:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN")

        if not OPENAI_API_KEY:
            return {
                "source": "whisper_genius",
                "ok": False,
                "error": "OPENAI_API_KEY non configurata",
            }

        # -------------------------------------------------------------
        # 1️⃣ TRASCRIZIONE AUDIO → TESTO (OpenAI Whisper API)
        # -------------------------------------------------------------
        openai.api_key = OPENAI_API_KEY
        with open(audio_path, "rb") as f:
            resp = openai.Audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="it"  # puoi cambiare in "auto" o "en"
            )

        transcript_text = resp.text.strip() if hasattr(resp, "text") else None
        if not transcript_text:
            return {
                "source": "whisper_genius",
                "ok": False,
                "error": "Whisper non ha generato testo valido"
            }

        print(f"🎙️ [Whisper] Trascrizione parziale: {transcript_text[:120]}...")

        # -------------------------------------------------------------
        # 2️⃣ RICERCA SU GENIUS
        # -------------------------------------------------------------
        if not GENIUS_API_TOKEN:
            print("⚠️ GENIUS_API_TOKEN mancante: salto ricerca su Genius")
            return {
                "source": "whisper_genius",
                "ok": True,
                "transcript": transcript_text,
                "results": [],
                "note": "GENIUS_API_TOKEN mancante"
            }

        headers = {"Authorization": f"Bearer {GENIUS_API_TOKEN}"}
        params = {"q": transcript_text}
        r = requests.get("https://api.genius.com/search", headers=headers, params=params, timeout=30)

        if r.status_code != 200:
            return {
                "source": "whisper_genius",
                "ok": False,
                "error": f"Genius API error {r.status_code}"
            }

        data = r.json()
        hits = data.get("response", {}).get("hits", [])

        if not hits:
            return {
                "source": "whisper_genius",
                "ok": True,
                "transcript": transcript_text,
                "results": [],
                "note": "Nessun risultato Genius"
            }

        results = []
        for hit in hits[:5]:
            song = hit["result"]
            results.append({
                "title": song["title"],
                "artist": song["primary_artist"]["name"],
                "url": song["url"],
                "source": "whisper_genius",
                "confidence": 0.6
            })

        print(f"🎵 [Genius] {len(results)} risultati trovati.")
        return {
            "source": "whisper_genius",
            "ok": True,
            "transcript": transcript_text,
            "results": results
        }

    except Exception as e:
        traceback.print_exc()
        return {
            "source": "whisper_genius",
            "ok": False,
            "error": str(e)
        }