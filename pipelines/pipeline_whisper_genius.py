import os
import time
from typing import Dict, Any

from openai import OpenAI
from pipelines.pipeline_genius_text import genius_search_list

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def run_whisper_genius(audio_path: str, top_k: int = 5) -> Dict[str, Any]:
    t0 = time.time()
    try:
        # 1) Trascrizione (no translate)
        with open(audio_path, "rb") as f:
            tr = client.audio.transcriptions.create(
                model="gpt-4o-transcribe",
                file=f,
                # niente language forzata → auto detect
                # temperature bassa per stabilità
                temperature=0.2,
            )
        transcript = (getattr(tr, "text", None) or "").strip()

        # Se nulla di utile, esci “ok=False”
        if not transcript:
            return {
                "source": "whisper_genius",
                "ok": False,
                "error": "transcript_empty",
                "elapsed_sec": round(time.time() - t0, 2),
            }

        # 2) Cerca su Genius usando il testo trascritto
        try:
            results = genius_search_list(transcript, top_k=top_k)
        except Exception as ge:
            return {
                "source": "whisper_genius",
                "ok": False,
                "error": f"genius_error: {ge}",
                "transcript": transcript,
                "elapsed_sec": round(time.time() - t0, 2),
            }

        return {
            "source": "whisper_genius",
            "ok": True,
            "transcript": transcript,     # mostriamo cosa ha capito
            "results": results,           # 👉 lista di canzoni url-apribili
            "elapsed_sec": round(time.time() - t0, 2),
        }
    except Exception as e:
        return {
            "source": "whisper_genius",
            "ok": False,
            "error": str(e),
            "elapsed_sec": round(time.time() - t0, 2),
        }