import os
import time
import hmac
import base64
import hashlib
from typing import Dict

import requests
from pydub import AudioSegment


def _prep_audio_for_acr(file_path: str) -> bytes:
    """
    Converte l'audio in WAV mono 16kHz e lo restituisce in bytes.
    """
    try:
        audio = AudioSegment.from_file(file_path)
        if len(audio) > 15000:
            audio = audio[:15000]
        audio = audio.set_channels(1).set_frame_rate(16000)

        # Esporta direttamente in memoria (senza file temporaneo)
        from io import BytesIO
        buf = BytesIO()
        audio.export(buf, format="wav")
        return buf.getvalue()
    except Exception as e:
        raise RuntimeError(f"prep_audio_failed: {e}")


def run_acrcloud(file_path: str) -> Dict:
    t0 = time.time()
    try:
        host = os.getenv("ACRCLOUD_HOST", "")
        key = os.getenv("ACRCLOUD_ACCESS_KEY", "")
        secret = os.getenv("ACRCLOUD_ACCESS_SECRET", "")

        if not host or not key or not secret:
            return {
                "source": "acrcloud",
                "ok": False,
                "error": "missing_credentials",
                "elapsed_sec": 0,
            }

        # Garantiamo schema
        host = host.strip().rstrip("/")
        if not host.startswith("http"):
            host = "https://" + host

        endpoint = "/v1/identify"
        url = f"{host}{endpoint}"

        # Prepara audio
        audio_data = _prep_audio_for_acr(file_path)

        timestamp = str(int(time.time()))
        string_to_sign = "\n".join(["POST", endpoint, key, "audio", "1", timestamp])
        sign = base64.b64encode(
            hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha1).digest()
        ).decode()

        data = {
            "access_key": key,
            "data_type": "audio",
            "signature_version": "1",
            "signature": sign,
            "timestamp": timestamp,
            "sample_bytes": len(audio_data),
        }

        files = {"sample": ("sample.wav", audio_data, "audio/wav")}
        r = requests.post(url, data=data, files=files, timeout=15)

        # --- risposta ---
        try:
            payload = r.json()
        except Exception:
            return {
                "source": "acrcloud",
                "ok": False,
                "error": f"HTTP {r.status_code}: {r.text[:200]}",
                "elapsed_sec": round(time.time() - t0, 2),
            }

        # --- analisi payload ---
        if payload.get("status", {}).get("code") == 0:
            music = payload.get("metadata", {}).get("music", [])
            if music:
                top = music[0]
                title = top.get("title", "Sconosciuto")
                artists = ", ".join(a.get("name", "") for a in top.get("artists", []))
                from requests.utils import quote
                genius_link = f"https://genius.com/search?q={quote((artists + ' ' + title).strip())}"
                return {
                    "source": "acrcloud",
                    "ok": True,
                    "title": title,
                    "artist": artists or "Sconosciuto",
                    "url": genius_link,
                    "elapsed_sec": round(time.time() - t0, 2),
                }

        # Nessun match
        return {
            "source": "acrcloud",
            "ok": False,
            "error": "Nessun brano riconosciuto",
            "elapsed_sec": round(time.time() - t0, 2),
        }

    except Exception as e:
        return {
            "source": "acrcloud",
            "ok": False,
            "error": str(e),
            "elapsed_sec": round(time.time() - t0, 2),
        }