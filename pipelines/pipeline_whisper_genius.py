import os
import re
import time
from typing import List, Dict, Any

import aiohttp
from openai import OpenAI

# Client OpenAI (senza parametri strani: niente proxies/messages)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN")  # opzionale ma consigliato
GENIUS_API_URL = "https://api.genius.com/search"

# ✅ Regex per escludere risultati con caratteri non latini
LATIN_PATTERN = re.compile(r"^[a-zA-Z0-9\s\-,.!?'\"éèàùìòç&()]+$", re.IGNORECASE)


async def _search_genius(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Cerca su Genius. Se ho il token uso l'API ufficiale, altrimenti ritorno
    un singolo link di ricerca web su genius.com come fallback “povero”.
    """
    if not query.strip():
        return []

    if not GENIUS_API_TOKEN:
        # Fallback senza token: link di ricerca su Genius
        q = query.replace(" ", "+")
        return [{"title": query, "artist": "", "url": f"https://genius.com/search?q={q}"}]

    headers = {"Authorization": f"Bearer {GENIUS_API_TOKEN}"}
    params = {"q": query}

    async with aiohttp.ClientSession() as session:
        async with session.get(GENIUS_API_URL, headers=headers, params=params, timeout=20) as resp:
            if resp.status != 200:
                txt = await resp.text()
                return [{"title": "Errore Genius", "artist": "", "url": None, "error": f"HTTP {resp.status}: {txt}"}]
            data = await resp.json()

    hits = data.get("response", {}).get("hits", [])[:top_k]
    out: List[Dict[str, Any]] = []
    for h in hits:
        r = h.get("result", {}) or {}
        title = r.get("title") or r.get("full_title") or "Senza titolo"
        artist = (r.get("primary_artist") or {}).get("name") or ""
        url = r.get("url")

        # ⚠️ Filtro per saltare risultati con caratteri non latini
        if not LATIN_PATTERN.match(title) or not LATIN_PATTERN.match(artist):
            continue

        out.append({"title": title, "artist": artist, "url": url})
    return out


async def run_whisper_genius(file_path: str) -> Dict[str, Any]:
    """
    1) Trascrive l’audio con Whisper (auto language)
    2) Cerca su Genius i brani compatibili con il testo trascritto
    """
    t0 = time.perf_counter()
    try:
        # ✅ Whisper transcribe (niente 'messages', niente 'auto' esplicito)
        with open(file_path, "rb") as f:
            tx = client.audio.transcriptions.create(
                model="whisper-1",   # puoi passare "gpt-4o-mini-transcribe" se preferisci
                file=f,
            )
        transcript = (tx.text or "").strip()
    except Exception as e:
        return {
            "source": "whisper_genius",
            "ok": False,
            "error": f"Transcription error: {e}",
            "elapsed_sec": round(time.perf_counter() - t0, 2),
        }

    if not transcript:
        return {
            "source": "whisper_genius",
            "ok": False,
            "error": "Nessuna trascrizione ottenuta",
            "elapsed_sec": round(time.perf_counter() - t0, 2),
        }

    # 🔎 Ricerca su Genius con la frase trascritta
    try:
        results = await _search_genius(transcript, top_k=5)
        return {
            "source": "whisper_genius",
            "ok": True,
            "transcript": transcript,
            "results": results,
            "elapsed_sec": round(time.perf_counter() - t0, 2),
        }
    except Exception as e:
        return {
            "source": "whisper_genius",
            "ok": False,
            "error": f"Genius search error: {e}",
            "transcript": transcript,
            "elapsed_sec": round(time.perf_counter() - t0, 2),
        }