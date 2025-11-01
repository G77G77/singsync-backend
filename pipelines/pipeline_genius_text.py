import os, requests, time

async def run_genius_text(query: str):
    start = time.time()
    try:
        token = os.getenv("GENIUS_API_TOKEN")
        if not token:
            raise RuntimeError("GENIUS_API_TOKEN mancante")

        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get("https://api.genius.com/search", headers=headers, params={"q": query})
        data = res.json()

        results = []
        for hit in data.get("response", {}).get("hits", [])[:5]:
            song = hit.get("result", {})
            results.append({
                "title": song.get("title"),
                "artist": song.get("primary_artist", {}).get("name"),
                "url": song.get("url"),
            })

        return {"ok": True, "results": results, "elapsed_sec": round(time.time() - start, 1)}
    except Exception as e:
        return {"ok": False, "error": str(e), "elapsed_sec": round(time.time() - start, 1)}