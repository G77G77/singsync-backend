import os
import hmac
import base64
import hashlib
import time
import requests
from pipelines.pipeline_genius_text import run_genius_text

def run_acrcloud(file_path: str):
    """Riconosce brano con ACRCloud e arricchisce con link Genius."""
    start = time.time()
    try:
        host = os.getenv("ACRCLOUD_HOST")
        access_key = os.getenv("ACRCLOUD_ACCESS_KEY")
        access_secret = os.getenv("ACRCLOUD_ACCESS_SECRET")

        if not host or not access_key or not access_secret:
            return {
                "source": "acrcloud",
                "ok": False,
                "error": "missing_credentials",
                "elapsed_sec": 0,
            }

        timestamp = str(int(time.time()))
        string_to_sign = f"POST\n/v1/identify\n{access_key}\naudio\n1\n{timestamp}"
        sign = base64.b64encode(
            hmac.new(
                access_secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha1,
            ).digest()
        ).decode("utf-8")

        with open(file_path, "rb") as f:
            sample_bytes = f.read()

        data = {
            "access_key": access_key,
            "sample_bytes": len(sample_bytes),
            "timestamp": timestamp,
            "signature": sign,
            "data_type": "audio",
            "signature_version": "1",
        }

        files = {"sample": sample_bytes}
        r = requests.post(f"https://{host}/v1/identify", files=files, data=data, timeout=15)

        res = r.json()
        elapsed = round(time.time() - start, 2)

        if "status" not in res or res["status"]["code"] != 0:
            return {
                "source": "acrcloud",
                "ok": False,
                "error": res.get("status", {}).get("msg", "Nessun brano riconosciuto"),
                "elapsed_sec": elapsed,
            }

        music_info = res["metadata"]["music"][0]
        title = music_info.get("title")
        artist = music_info.get("artists", [{}])[0].get("name")

        # 🔗 Cerca anche su Genius usando la pipeline testuale
        genius_match = await_genius_result(title, artist)

        return {
            "source": "acrcloud",
            "ok": True,
            "title": title,
            "artist": artist,
            "url": genius_match,
            "elapsed_sec": elapsed,
        }

    except Exception as e:
        return {
            "source": "acrcloud",
            "ok": False,
            "error": str(e),
            "elapsed_sec": round(time.time() - start, 2),
        }


def await_genius_result(title: str, artist: str) -> str:
    """Chiama la ricerca Genius per ottenere il link lyrics."""
    try:
        query = f"{artist} {title}"
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_genius_text(query))
        loop.close()

        if result and "results" in result and len(result["results"]) > 0:
            return result["results"][0].get("url", "")
        return ""
    except Exception:
        return ""