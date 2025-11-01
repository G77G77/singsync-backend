# pipelines/pipeline_acrcloud.py
import os
import time
import hmac
import base64
import hashlib
import json
import requests
from typing import Dict, Any

def _first_env(*names: str) -> str | None:
    """Ritorna il primo env var non vuoto tra i nomi passati."""
    for n in names:
        v = os.getenv(n)
        if v and str(v).strip():
            return str(v).strip()
    return None

def _pick_credentials() -> Dict[str, str | None]:
    # Supporta tutte le varianti viste in passato
    host = _first_env("ACRCLOUD_HOST", "ARCCLOUD_HOST", "ARCLOUD_HOST")
    access_key = _first_env("ACRCLOUD_ACCESS_KEY", "ARCCLOUD_ACCESS_KEY", "ARCLOUD_ACCESS_KEY")
    access_secret = _first_env("ACRCLOUD_ACCESS_SECRET", "ARCCLOUD_ACCESS_SECRET", "ARCLOUD_ACCESS_SECRET")
    return {"host": host, "access_key": access_key, "access_secret": access_secret}

def _mask(v: str | None) -> str:
    if not v:
        return "<none>"
    if len(v) <= 6:
        return "***"
    return v[:3] + "…" + v[-3:]

def run_acrcloud(token: str, file_path: str) -> Dict[str, Any]:
    """
    Esegue riconoscimento su ACRCloud.
    Ritorna un dict in formato card:
      {source:"acrcloud", ok:bool, title?, artist?, url?, elapsed_sec, error?}
    """
    t0 = time.time()
    source = "acrcloud"

    creds = _pick_credentials()
    host = creds["host"]
    access_key = creds["access_key"]
    access_secret = creds["access_secret"]

    # Log diagnostico “sicuro”
    print(
        f"[ACRCloud] host={host or '<none>'} "
        f"key={_mask(access_key)} secret={_mask(access_secret)}"
    )

    if not host or not access_key or not access_secret:
        return {
            "source": source,
            "ok": False,
            "error": "missing_credentials",
            "elapsed_sec": round(time.time() - t0, 2),
        }

    # Costruzione firma (ACRCloud standard)
    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(int(time.time()))

    string_to_sign = "\n".join([
        http_method,
        http_uri,
        access_key,
        data_type,
        signature_version,
        timestamp
    ])
    sign = base64.b64encode(
        hmac.new(
            access_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha1
        ).digest()
    ).decode("utf-8")

    files = {
        "sample": open(file_path, "rb"),
        "sample_bytes": str(os.path.getsize(file_path))
    }
    data = {
        "access_key": access_key,
        "data_type": data_type,
        "signature_version": signature_version,
        "signature": sign,
        "timestamp": timestamp
    }

    try:
        url = f"https://{host}/v1/identify"
        resp = requests.post(url, files=files, data=data, timeout=15)
        elapsed = round(time.time() - t0, 2)

        if resp.status_code == 401:
            # credenziali sbagliate
            return {
                "source": source,
                "ok": False,
                "error": "invalid_credentials",
                "elapsed_sec": elapsed,
            }

        if resp.status_code != 200:
            return {
                "source": source,
                "ok": False,
                "error": f"http_{resp.status_code}",
                "elapsed_sec": elapsed,
            }

        j = resp.json()

        # ACRCloud: quando non trova match
        if j.get("status", {}).get("code") != 0:
            return {
                "source": source,
                "ok": False,
                "error": "no_match",
                "elapsed_sec": elapsed,
            }

        md = (j.get("metadata") or {}).get("music") or []
        if not md:
            return {
                "source": source,
                "ok": False,
                "error": "no_match",
                "elapsed_sec": elapsed,
            }

        # Prendi il primo match
        m0 = md[0]
        title = m0.get("title")
        artists = m0.get("artists") or []
        artist = artists[0].get("name") if artists else None

        # Prova a comporre un url lyrics (search)
        url_guess = None
        if title or artist:
            url_guess = f"https://genius.com/search?q={requests.utils.quote((artist or '') + ' ' + (title or ''))}"

        return {
            "source": source,
            "ok": True,
            "title": title,
            "artist": artist,
            "url": url_guess,
            "elapsed_sec": elapsed,
        }

    except Exception as e:
        return {
            "source": source,
            "ok": False,
            "error": f"exception:{e}",
            "elapsed_sec": round(time.time() - t0, 2),
        }
    finally:
        try:
            files["sample"].close()
        except Exception:
            pass