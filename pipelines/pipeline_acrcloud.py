import os
import time
import hmac
import base64
import hashlib
import requests
from typing import Dict, Any

def _acrcloud_disabled() -> bool:
    return os.getenv("ENABLE_ACRCLOUD", "1") != "1"

def _build_acr_signature(access_key: str, access_secret: str, timestamp: str) -> str:
    """
    Firma secondo le specifiche ACRCloud identify v1
    StringToSign:
      "POST\n/v1/identify\n{access_key}\naudio\n1\n{timestamp}"
    HMAC-SHA1 con secret, poi base64
    """
    string_to_sign = "\n".join(["POST", "/v1/identify", access_key, "audio", "1", timestamp])
    sign = hmac.new(access_secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(sign).decode("utf-8")

def run_acrcloud(audio_path: str) -> Dict[str, Any]:
    if _acrcloud_disabled():
        return {"source": "acrcloud", "ok": False, "disabled": True}

    access_key = os.getenv("ARCCLOUD_ACCESS_KEY", "")
    access_secret = os.getenv("ARCCLOUD_ACCESS_SECRET", "")
    host = os.getenv("ARCCLOUD_HOST", "").rstrip("/")
    if not (access_key and access_secret and host):
        return {"source": "acrcloud", "ok": False, "error": "missing_credentials"}

    try:
        with open(audio_path, "rb") as f:
            sample_bytes = f.read()

        timestamp = str(int(time.time()))
        signature = _build_acr_signature(access_key, access_secret, timestamp)

        data = {
            "access_key": access_key,
            "data_type": "audio",
            "signature_version": "1",
            "signature": signature,
            "timestamp": timestamp,
        }
        files = {
            "sample": ("audio.wav", sample_bytes, "audio/wav"),
            "sample_bytes": (None, str(len(sample_bytes))),
        }

        url = f"{host}/v1/identify"
        resp = requests.post(url, data=data, files=files, timeout=30)
        jr = resp.json()

        # Parsing robusto (ACRCloud può restituire più matches)
        results = []
        status_code = (jr.get("status") or {}).get("code", -1)
        if status_code == 0:
            # hits in metadata.music
            for m in (jr.get("metadata", {}).get("music") or [])[:3]:
                title = m.get("title")
                artists = m.get("artists") or []
                artist = ", ".join([a.get("name", "") for a in artists if a.get("name")])
                # Alcuni provider
                url_link = ""
                image = ""
                preview = ""
                external_metadata = m.get("external_metadata", {})

                # Spotify
                sp = external_metadata.get("spotify", {})
                sp_track = (sp.get("track") or {})
                if not url_link:
                    url_link = sp_track.get("external_urls", {}).get("spotify", "")
                if not preview:
                    preview = sp_track.get("preview_url", "")
                if not image:
                    imgs = (sp.get("album") or {}).get("images", [])
                    if imgs:
                        image = imgs[0].get("url", "")

                # Deezer / YouTube fallback semplici
                dz = external_metadata.get("deezer", {})
                if not url_link:
                    url_link = (dz.get("track") or {}).get("link", "") or url_link

                yt = external_metadata.get("youtube", {})
                if not url_link:
                    url_link = f"https://www.youtube.com/watch?v={ (yt.get('vid') or '') }" if yt.get("vid") else url_link

                results.append({
                    "title": title or "",
                    "artist": artist or "",
                    "url": url_link,
                    "preview": preview,
                    "image": image,
                    "source": "acrcloud",
                    "confidence": 0.85
                })

        return {"source": "acrcloud", "ok": True, "results": results}
    except Exception as e:
        return {"source": "acrcloud", "ok": False, "error": str(e)}