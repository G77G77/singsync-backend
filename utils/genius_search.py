import os
import aiohttp

GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN", "")

async def search_genius_text(query: str):
    """
    Ricerca su Genius API (solo testo libero).
    """
    if not GENIUS_API_TOKEN:
        raise ValueError("GENIUS_API_TOKEN non impostato")

    headers = {"Authorization": f"Bearer {GENIUS_API_TOKEN}"}
    url = f"https://api.genius.com/search?q={query}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()

    hits = data.get("response", {}).get("hits", [])
    results = []
    for h in hits[:5]:
        result = h["result"]
        results.append({
            "title": result["title"],
            "artist": result["primary_artist"]["name"],
            "url": result["url"],
        })
    return results