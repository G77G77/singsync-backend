import os
import aiohttp
from typing import List, Dict

GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN")

BASE_URL = "https://api.genius.com/search"

async def run_genius_text(query: str) -> Dict[str, any]:
    """Cerca su Genius i testi relativi a una query testuale."""
    if not GENIUS_API_TOKEN:
        return {
            "source": "genius",
            "ok": False,
            "error": "GENIUS_API_TOKEN non configurato",
        }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                BASE_URL,
                headers={"Authorization": f"Bearer {GENIUS_API_TOKEN}"},
                params={"q": query},
                timeout=10
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return {"ok": False, "error": f"HTTP {resp.status}: {text}"}

                data = await resp.json()
                hits = data.get("response", {}).get("hits", [])
                results: List[Dict[str, str]] = []

                for hit in hits[:5]:  # massimo 5 risultati
                    result = hit.get("result", {})
                    results.append({
                        "title": result.get("title", "Sconosciuto"),
                        "artist": result.get("primary_artist", {}).get("name", ""),
                        "url": result.get("url"),
                        "source": "genius",
                        "ok": True
                    })

                if not results:
                    return {"ok": False, "error": "Nessun risultato trovato"}

                return {"ok": True, "results": results}

    except Exception as e:
        return {"ok": False, "error": str(e)}