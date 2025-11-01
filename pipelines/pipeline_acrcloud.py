import os, time, hmac, base64, hashlib, requests

ACR_HOST = os.getenv("ACRCLOUD_HOST")
ACR_ACCESS_KEY = os.getenv("ACRCLOUD_ACCESS_KEY")
ACR_ACCESS_SECRET = os.getenv("ACRCLOUD_ACCESS_SECRET")

async def run_acrcloud(audio_path: str):
    start = time.time()
    try:
        if not ACR_ACCESS_KEY or not ACR_ACCESS_SECRET or not ACR_HOST:
            return {"source": "acrcloud", "ok": False, "error": "missing_credentials", "elapsed_sec": 0}

        http_method = "POST"
        http_uri = "/v1/identify"
        timestamp = str(int(time.time()))
        signature_raw = f"{http_method}\n{http_uri}\n{ACR_ACCESS_KEY}\naudio\n1\n{timestamp}".encode("utf-8")

        sign = base64.b64encode(hmac.new(ACR_ACCESS_SECRET.encode("utf-8"), signature_raw, digestmod=hashlib.sha1).digest()).decode("utf-8")

        files = [
            ("sample", open(audio_path, "rb")),
            ("access_key", (None, ACR_ACCESS_KEY)),
            ("sample_bytes", (None, str(os.path.getsize(audio_path)))),
            ("timestamp", (None, timestamp)),
            ("signature", (None, sign)),
            ("data_type", (None, "audio")),
            ("signature_version", (None, "1")),
        ]

        url = f"https://{ACR_HOST}/v1/identify"
        res = requests.post(url, files=files, timeout=15)
        data = res.json()
        music = data.get("metadata", {}).get("music", [])
        if not music:
            raise ValueError("Nessun brano riconosciuto")

        best = music[0]
        return {
            "source": "acrcloud",
            "ok": True,
            "title": best.get("title"),
            "artist": best.get("artists", [{}])[0].get("name"),
            "elapsed_sec": round(time.time() - start, 1),
        }
    except Exception as e:
        return {"source": "acrcloud", "ok": False, "error": str(e), "elapsed_sec": round(time.time() - start, 1)}