import os
import base64
import hmac
import hashlib
import time
import json
import aiohttp

ACR_HOST = os.getenv("ACRCLOUD_HOST", "https://identify-eu-west-1.acrcloud.com")
ACR_ACCESS_KEY = os.getenv("ACRCLOUD_ACCESS_KEY")
ACR_ACCESS_SECRET = os.getenv("ACRCLOUD_ACCESS_SECRET")

async def run_acrcloud(token: str, file_path: str):
    """Identifica un brano tramite ACRCloud e genera link Genius."""
    start = time.time()

    if not all([ACR_HOST, ACR_ACCESS_KEY, ACR_ACCESS_SECRET]):
        return {
            "source": "acrcloud",
            "ok": False,
            "error": "missing_credentials",
            "elapsed_sec": 0,
        }

    try:
        # ✅ Ensure full https:// scheme
        host = ACR_HOST.strip()
        if not host.startswith("http"):
            host = f"https://{host}"

        # Firma richiesta ACRCloud
        string_to_sign = f"POST\n/v1/identify\n{ACR_ACCESS_KEY}\naudio\n1\n{int(time.time())}"
        sign = base64.b64encode(
            hmac.new(
                ACR_ACCESS_SECRET.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha1,
            ).digest()
        ).decode("utf-8")

        with open(file_path, "rb") as f:
            sample_bytes = f.read()

        form = aiohttp.FormData()
        form.add_field("sample", sample_bytes, filename="sample.wav", content_type="audio/wav")
        form.add_field("access_key", ACR_ACCESS_KEY)
        form.add_field("data_type", "audio")
        form.add_field("signature_version", "1")
        form.add_field("signature", sign)
        form.add_field("timestamp", str(int(time.time())))

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{host}/v1/identify", data=form) as resp:
                text = await resp.text()
                data = json.loads(text)

        elapsed = round(time.time() - start, 2)

        if "metadata" not in data:
            return {
                "source": "acrcloud",
                "ok": False,
                "error": "Nessun brano riconosciuto",
                "elapsed_sec": elapsed,
            }

        music = data["metadata"]["music"][0]
        title = music.get("title", "Sconosciuto")
        artist = music["artists"][0]["name"] if music.get("artists") else "Sconosciuto"

        # ✅ Link Genius generato automaticamente
        search_query = f"{artist} {title}".replace(" ", "+")
        genius_url = f"https://genius.com/search?q={search_query}"

        return {
            "source": "acrcloud",
            "ok": True,
            "title": title,
            "artist": artist,
            "url": genius_url,
            "elapsed_sec": elapsed,
        }

    except Exception as e:
        elapsed = round(time.time() - start, 2)
        return {
            "source": "acrcloud",
            "ok": False,
            "error": str(e),
            "elapsed_sec": elapsed,
        }