import os
import requests
from typing import Dict, Any, List

OPENAI_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")  # o "gpt-4o-mini-transcribe"

def _wg_disabled() -> bool:
    return os.getenv("ENABLE_WHISPER_GENIUS", "1") != "1"

def _openai_transcribe_wav(path: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")

    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    with open(path, "rb") as f:
        files = {"file": (os.path.basename(path), f, "audio/wav")}
        data = {"model": OPENAI_MODEL, "language": "auto"}
        r = requests.post(url, headers=headers, files=files, data=data, timeout=60)
    jr = r.json()
    if "error" in jr:
        raise RuntimeError(jr["error"])
    return (jr.get("text") or "").strip()

def _genius_search(q: str) -> List[Dict[str, Any]]:
    token = os.getenv("GENIUS_API_TOKEN", "")
    if not (token and q):
        return []
    try:
        h = {"Authorization": f"Bearer {token}"}
        r = requests.get("https://api.genius.com/search", headers=h, params={"q": q}, timeout=20)
        data = r.json()
        out = []
        for hit in (data.get("response", {}).get("hits") or [])[:5]:
            s = hit.get("result", {})
            out.append({
                "title": s.get("title") or "",
                "artist": (s.get("primary_artist") or {}).get("name", ""),
                "url": s.get("url") or "",
                "preview": "",
                "image": (s.get("song_art_image_url") or s.get("header_image_url") or ""),
                "source": "whisper+genius",
                "confidence": 0.6
            })
        return out
    except Exception:
        return []

def run_whisper_genius(audio_path: str) -> Dict[str, Any]:
    if _wg_disabled():
        return {"source": "whisper_genius", "ok": False, "disabled": True}
    try:
        text = _openai_transcribe_wav(audio_path)
        results = _genius_search(text) if text else []
        return {
            "source": "whisper_genius",
            "ok": True,
            "query": text,
            "results": results
        }
    except Exception as e:
        return {"source": "whisper_genius", "ok": False, "error": str(e)}