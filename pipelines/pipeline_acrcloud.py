# pipelines/pipeline_acrcloud.py
import os
import time
import hmac
import json
import base64
import hashlib
from typing import Dict

import requests
from pydub import AudioSegment


def _prep_audio_for_acr(src_path: str) -> str:
    """
    Converte l'audio in WAV, mono, 16kHz e tronca ai primi ~15s.
    ACRCloud riconosce molto meglio così.
    Ritorna il path del file temporaneo pronto per l'upload.
    """
    audio = AudioSegment.from_file(src_path)
    if len(audio) > 15000:
        audio = audio[:15000]
    audio = audio.set_channels(1).set_frame_rate(16000)

    tmp_path = f"/tmp/acr_{int(time.time()*1000)}.wav"
    audio.export(tmp_path, format="wav")
    return tmp_path


def run_acrcloud(file_path: str) -> Dict:
    t0 = time.time()

    host = os.getenv("ACRCLOUD_HOST", "")
    access_key = os.getenv("ACRCLOUD_ACCESS_KEY", "")
    access_secret = os.getenv("ACRCLOUD_ACCESS_SECRET", "")

    if not host or not access_key or not access_secret:
        return {
            "source": "acrcloud",
            "ok": False,
            "error": "missing_credentials",
            "elapsed_sec": 0,
        }

    # host deve avere lo schema
    host = host.strip().rstrip("/")
    if not host.startswith("http"):
        host = "https://" + host
    endpoint = "/v1/identify"
    url = f"{host}{endpoint}"

    # Prepara audio in formato "amico" di ACR
    tmp_path = _prep_audio_for_acr(file_path)

    try:
        with open(tmp_path, "rb") as f:
            sample = f.read()

        timestamp = str(int(time.time()))
        string_to_sign = "\n".join(
            ["POST", endpoint, access_key, "audio", "1", timestamp]
        )
        signature = base64.b64encode(
            hmac.new(
                access_secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha1,
            ).digest()
        ).decode("utf-8")

        data = {
            "access_key": access_key,
            "data_type": "audio",
            "signature_version": "1",
            "signature": signature,
            "timestamp": timestamp,
            "sample_bytes": len(sample),
        }
        files = {"sample": ("audio.wav", sample, "audio/wav")}

        r = requests.post(url, data=data, files=files, timeout=15)
        # In caso di risposte non-JSON, falliamo con messaggio chiaro
        try:
            payload = r.json()
        except Exception:
            return {
                "source": "acrcloud",
                "ok": False,
                "error": f"HTTP {r.status_code}: {r.text[:200]}",
                "elapsed_sec": round(time.time() - t0, 2),
            }

        # Status OK
        if payload.get("status", {}).get("code") == 0:
            music = payload.get("metadata", {}).get("music", []) or []
            if music:
                top = music[0]
                title = top.get("title") or ""
                artists = ", ".join(
                    a.get("name", "") for a in (top.get("artists") or []) if a.get("name")
                )
                # link utile (ricerca lyrics su Genius)
                from requests.utils import quote
                genius_search = f"https://genius.com/search?q={quote((artists + ' ' + title).strip())}"

                return {
                    "source": "acrcloud",
                    "ok": True,
                    "title": title or "Sconosciuto",
                    "artist": artists or "Sconosciuto",
                    "url": genius_search,
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
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass