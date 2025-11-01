import os
import time
import base64
import hmac
import hashlib
import json
import aiohttp
import tempfile
import subprocess


async def run_acrcloud(file_path: str) -> dict:
    """Identifica il brano tramite ACRCloud."""
    start = time.time()

    host = os.getenv("ACRCLOUD_HOST")
    access_key = os.getenv("ACRCLOUD_ACCESS_KEY")
    access_secret = os.getenv("ACRCLOUD_ACCESS_SECRET")

    if not host or not access_key or not access_secret:
        return {
            "source": "acrcloud",
            "ok": False,
            "error": "missing_credentials",
            "elapsed_sec": 0
        }

    try:
        # ✅ Forza conversione in WAV 16k mono per compatibilità ACRCloud
        wav_path = tempfile.mktemp(suffix=".wav")
        subprocess.run([
            "ffmpeg", "-y", "-i", file_path,
            "-ar", "16000", "-ac", "1", wav_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Leggi il file convertito
        with open(wav_path, "rb") as f:
            sample_bytes = f.read()

        timestamp = str(int(time.time()))
        string_to_sign = "\n".join([
            "POST",
            "/v1/identify",
            access_key,
            "audio",
            "1",
            timestamp
        ])
        sign = base64.b64encode(
            hmac.new(
                access_secret.encode("ascii"),
                string_to_sign.encode("ascii"),
                digestmod=hashlib.sha1
            ).digest()
        ).decode("ascii")

        data = aiohttp.FormData()
        data.add_field("sample", sample_bytes, filename="sample.wav")
        data.add_field("access_key", access_key)
        data.add_field("data_type", "audio")
        data.add_field("signature_version", "1")
        data.add_field("signature", sign)
        data.add_field("timestamp", timestamp)

        async with aiohttp.ClientSession() as session:
            async with session.post(f"https://{host}/v1/identify", data=data) as resp:
                text = await resp.text()
                try:
                    result = json.loads(text)
                except Exception:
                    result = {"error": text}

        os.remove(wav_path)

        if "metadata" not in result or "music" not in result["metadata"]:
            return {
                "source": "acrcloud",
                "ok": False,
                "error": "Nessun brano riconosciuto",
                "elapsed_sec": round(time.time() - start, 2)
            }

        music = result["metadata"]["music"][0]
        title = music.get("title", "Sconosciuto")
        artist = ", ".join(a["name"] for a in music.get("artists", [])) if music.get("artists") else "Sconosciuto"

        return {
            "source": "acrcloud",
            "ok": True,
            "title": title,
            "artist": artist,
            "elapsed_sec": round(time.time() - start, 2)
        }

    except Exception as e:
        return {
            "source": "acrcloud",
            "ok": False,
            "error": str(e),
            "elapsed_sec": round(time.time() - start, 2)
        }