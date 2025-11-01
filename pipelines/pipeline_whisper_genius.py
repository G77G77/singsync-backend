import os, time, requests
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def run_whisper_genius(audio_path: str):
    start = time.time()
    try:
        lang = os.getenv("WHISPER_LANG", "auto").lower()
        langs_to_try = ["it", "en"] if lang == "auto" else [lang]
        transcript_text = None
        last_error = None

        for l in langs_to_try:
            try:
                with open(audio_path, "rb") as f:
                    t = client.audio.transcriptions.create(model="whisper-1", file=f, language=l)
                transcript_text = t.text.strip()
                break
            except Exception as e:
                last_error = str(e)

        if not transcript_text:
            raise RuntimeError(last_error or "Whisper transcription failed")

        genius_token = os.getenv("GENIUS_API_TOKEN")
        if not genius_token:
            raise RuntimeError("GENIUS_API_TOKEN mancante")

        headers = {"Authorization": f"Bearer {genius_token}"}
        res = requests.get("https://api.genius.com/search", headers=headers, params={"q": transcript_text[:100]})
        data = res.json()

        hits = data.get("response", {}).get("hits", [])
        songs = [{"title": h["result"]["title"], "artist": h["result"]["primary_artist"]["name"], "url": h["result"]["url"]} for h in hits[:5]]

        return {
            "source": "whisper_genius",
            "ok": True,
            "elapsed_sec": round(time.time() - start, 1),
            "transcript": transcript_text,
            "results": songs,
        }
    except Exception as e:
        return {"source": "whisper_genius", "ok": False, "error": str(e), "elapsed_sec": round(time.time() - start, 1)}