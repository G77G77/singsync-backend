import os
import time
import requests

GENIUS_TOKEN = os.getenv("GENIUS_API_TOKEN")
ACR_HOST = os.getenv("ACRCLOUD_HOST")
ACR_KEY = os.getenv("ACRCLOUD_ACCESS_KEY")
ACR_SECRET = os.getenv("ACRCLOUD_ACCESS_SECRET")

async def run_acrcloud(token: str, file_path: str):
    start = time.time()

    if not (ACR_HOST and ACR_KEY and ACR_SECRET):
        return {
            "source": "acrcloud",
            "ok": False,
            "error": "missing_credentials",
            "elapsed_sec": 0
        }

    try:
        # Invia audio al servizio ACRCloud
        files = {"sample": open(file_path, "rb")}
        data = {"access_key": ACR_KEY, "data_type": "audio", "signature_version": "1"}
        r = requests.post(ACR_HOST, files=files, data=data, timeout=30)
        res = r.json()

        if "metadata" not in res:
            return {
                "source": "acrcloud",
                "ok": False,
                "error": "Nessun brano riconosciuto",
                "elapsed_sec": round(time.time() - start, 2)
            }

        music = res["metadata"]["music"][0]
        title = music.get("title", "Sconosciuto")
        artist = music["artists"][0].get("name", "Sconosciuto")

        # ✅ Cerca URL su Genius
        genius_url = None
        if GENIUS_TOKEN:
            query = f"{title} {artist}"
            headers = {"Authorization": f"Bearer {GENIUS_TOKEN}"}
            g = requests.get(f"https://api.genius.com/search?q={query}", headers=headers, timeout=15)
            gdata = g.json()
            hits = gdata.get("response", {}).get("hits", [])
            if hits:
                genius_url = hits[0]["result"]["url"]

        return {
            "source": "acrcloud",
            "ok": True,
            "title": title,
            "artist": artist,
            "url": genius_url,
            "elapsed_sec": round(time.time() - start, 2)
        }

    except Exception as e:
        return {
            "source": "acrcloud",
            "ok": False,
            "error": str(e),
            "elapsed_sec": round(time.time() - start, 2)
        }