import os
import time
import json
import hmac
import base64
import hashlib
import requests
from typing import Dict, Any

MOCK = os.getenv("MOCK_PIPELINES", "0") == "1"

def _acrcloud_signature(access_secret, data_type, signature_version, timestamp):
    sign_str = f"POST\n/v1/identify\n{access_secret}\n{data_type}\n{signature_version}\n{timestamp}"
    dig = hmac.new(access_secret.encode(), sign_str.encode(), hashlib.sha1).digest()
    return base64.b64encode(dig).decode()

def _acrcloud_request(file_path: str) -> Dict[str, Any]:
    """
    Secondo ACRCloud (identify API). Richiede:
    - ARCCLOUD_ACCESS_KEY
    - ARCCLOUD_ACCESS_SECRET
    - ARCCLOUD_HOST (es: https://identify-eu-west-1.acrcloud.com)
    """
    access_key   = os.getenv("ARCCLOUD_ACCESS_KEY")
    access_secret= os.getenv("ARCCLOUD_ACCESS_SECRET")
    host         = os.getenv("ARCCLOUD_HOST", "https://identify-eu-west-1.acrcloud.com")

    if not access_key or not access_secret:
        raise RuntimeError("ACRCloud chiavi non configurate")

    endpoint = host.rstrip("/") + "/v1/identify"
    data_type = "audio"
    sig_ver = "1"
    ts = str(int(time.time()))

    sign = _acrcloud_signature(access_secret, data_type, sig_ver, ts)

    files = {"sample": open(file_path, "rb")}
    data = {
        "access_key": access_key,
        "sample_bytes": os.path.getsize(file_path),
        "timestamp": ts,
        "signature": sign,
        "data_type": data_type,
        "signature_version": sig_ver,
    }
    r = requests.post(endpoint, files=files, data=data, timeout=50)
    return r.json()

async def run_acrcloud(file_path: str) -> Dict[str, Any]:
    source = "acrcloud"
    if MOCK:
        # simulazione con latenza
        import asyncio
        await asyncio.sleep(2.5)
        return {
            "source": source, "ok": True,
            "results": [{
                "title": "Mock ACR Result",
                "artist": "Mock Artist",
                "confidence": 0.85,
                "url": "",
                "preview": "",
                "image": ""
            }]
        }

    try:
        jr = _acrcloud_request(file_path)
        # parsing risultato
        res = []
        status = jr.get("status", {})
        if status.get("msg") == "Success":
            metadata = jr.get("metadata", {})
            music = metadata.get("music", [])
            for m in music[:3]:
                title = m.get("title")
                artists = ", ".join([a.get("name") for a in m.get("artists", []) if a.get("name")])
                url = ""
                # prova info extra
                external_metadata = m.get("external_metadata", {})
                spotify = external_metadata.get("spotify", {})
                if isinstance(spotify, dict) and "track" in spotify:
                    url = spotify["track"].get("link", "") or ""
                image = ""
                if "album" in m and "images" in m["album"]:
                    # non sempre presente, fallback vuoto
                    pass

                res.append({
                    "title": title or "",
                    "artist": artists or "",
                    "confidence": float(m.get("score", 80)) / 100.0,  # euristico
                    "url": url,
                    "preview": "",
                    "image": image
                })
            return {"source": source, "ok": True, "results": res}
        else:
            return {"source": source, "ok": False, "error": status.get("msg", "Unknown")}
    except Exception as e:
        return {"source": source, "ok": False, "error": str(e)}