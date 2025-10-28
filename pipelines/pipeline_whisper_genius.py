import os
import requests
from typing import Dict, Any, List

MOCK = os.getenv("MOCK_PIPELINES", "0") == "1"

def _openai_transcribe_wav(path: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY non configurata")
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    with open(path, "rb") as f:
        files = {"file": (os.path.basename(path), f, "audio/wav")}
        data = {"model": "whisper-1"}
        r = requests.post(url, headers=headers, data=data, files=files, timeout=60)
    jr = r.json()
    if "error" in jr:
        raise RuntimeError(jr["error"])
    return jr.get("text", "").strip()

def _genius_search(q: str) -> List[Dict[str, Any]]:
    token = os.getenv("GENIUS_API_TOKEN")
    out = []
    if not token or not q:
        return out
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get("https://api.genius.com/search", headers=headers, params={"q": q}, timeout=15)
        data = r.json()
        for hit in data.get("response", {}).get("hits", []):
            s = hit.get("result", {})
            out.append({
                "title": s.get("title", ""),
                "artist": (s.get("primary_artist") or {}).get("name", ""),
                "confidence": 0.5,
                "url": s.get("url", ""),
                "preview": "",
                "image": ""
            })
    except Exception as e:
        out = []
    return out

async def run_whisper_genius(file_path: str) -> Dict[str, Any]:
    source = "whisper_genius"
    if MOCK:
        import asyncio
        await asyncio.sleep(3.3)
        return {
            "source": source, "ok": True,
            "query": "mock transcript text here",
            "results": [{
                "title": "Mock Genius Title",
                "artist": "Mock Artist",
                "confidence": 0.55,
                "url": "https://genius.com/",
                "preview": "",
                "image": ""
            }]
        }

    try:
        text = _openai_transcribe_wav(file_path)
        results = _genius_search(text)
        return {"source": source, "ok": True, "query": text, "results": results}
    except Exception as e:
        return {"source": source, "ok": False, "error": str(e)}