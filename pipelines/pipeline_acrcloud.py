import os
import time
from typing import Dict, Any, Optional

import requests
from pipelines.pipeline_genius_text import genius_link_for

ACR_HOST = os.getenv("ACRCLOUD_HOST") or os.getenv("ACR_HOST")
ACR_KEY  = os.getenv("ACRCLOUD_KEY") or os.getenv("ACR_KEY")
ACR_SEC  = os.getenv("ACRCLOUD_SECRET") or os.getenv("ACR_SECRET")

async def run_acrcloud(audio_path: str) -> Dict[str, Any]:
    t0 = time.time()
    try:
        if not (ACR_HOST and ACR_KEY and ACR_SEC):
            return {
                "source": "acrcloud",
                "ok": False,
                "error": "missing_credentials",
                "elapsed_sec": 0,
            }

        # ... (qui usa il tuo codice già esistente per inviare a ACR e leggere la risposta) ...
        # Supponiamo di aver ottenuto:
        #   title, artist, preview_url = ...
        # Se il match fallisce:
        # return {"source":"acrcloud","ok":False,"error":"no_match", "elapsed_sec": round(time.time()-t0,2)}

        # ESEMPIO (placeholder): rimpiazza con il tuo parsing reale
        title: Optional[str] = None
        artist: Optional[str] = None
        preview_url: Optional[str] = None
        # TODO: assegna title/artist/preview_url dai dati ACR

        if not title and not artist:
            return {
                "source": "acrcloud",
                "ok": False,
                "error": "Nessun brano riconosciuto",
                "elapsed_sec": round(time.time() - t0, 2),
            }

        # 👉 Arricchiamo con il link ai lyrics su Genius
        url = None
        try:
            url = genius_link_for(title or "", artist)
        except Exception:
            pass

        return {
            "source": "acrcloud",
            "ok": True,
            "title": title,
            "artist": artist,
            "preview_url": preview_url,
            "url": url,   # <— link apribile ai lyrics se disponibile
            "elapsed_sec": round(time.time() - t0, 2),
        }
    except Exception as e:
        return {
            "source": "acrcloud",
            "ok": False,
            "error": str(e),
            "elapsed_sec": round(time.time() - t0, 2),
        }