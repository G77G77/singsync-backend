import os
import requests
from typing import List, Dict, Any, Optional

GENIUS_API = "https://api.genius.com/search"

def _genius_headers() -> Dict[str, str]:
    token = os.getenv("GENIUS_API_TOKEN") or os.getenv("GENIUS_TOKEN")
    if not token:
        raise RuntimeError("GENIUS_API_TOKEN mancante")
    return {"Authorization": f"Bearer {token}"}

def genius_search_list(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Ritorna una lista di {title, artist, url} per una query testo su Genius.
    """
    headers = _genius_headers()
    r = requests.get(GENIUS_API, headers=headers, params={"q": query}, timeout=10)
    r.raise_for_status()
    data = r.json()
    out: List[Dict[str, Any]] = []
    for hit in (data.get("response", {}) or {}).get("hits", [])[:top_k]:
        res = hit.get("result", {}) or {}
        title = res.get("title") or res.get("full_title") or ""
        primary = (res.get("primary_artist") or {}).get("name") or ""
        url = res.get("url") or None
        if title or primary or url:
            out.append({"title": title, "artist": primary, "url": url})
    return out

def genius_link_for(title: str, artist: Optional[str] = None) -> Optional[str]:
    """
    Trova il miglior link Genius per title (+ artist se presente).
    """
    q = f"{artist} {title}".strip() if artist else title
    results = genius_search_list(q, top_k=1)
    return results[0]["url"] if results else None

# Endpoint testuale già usato da /identify_text
async def run_genius_text(query: str, top_k: int = 5) -> Dict[str, Any]:
    try:
        results = genius_search_list(query, top_k=top_k)
        return {"ok": True, "source": "genius_text", "query": query, "results": results}
    except Exception as e:
        return {"ok": False, "source": "genius_text", "error": str(e)}