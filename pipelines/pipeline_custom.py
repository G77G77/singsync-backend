import os
import time
from typing import Dict, Any

# Nota: la vera Fase 1–3 (Librosa/CREPE/OpenL3) può essere pesante su Render.
# Qui lasciamo un placeholder veloce e sicuro (mock) finché non attiviamo il modello.
MOCK = os.getenv("MOCK_PIPELINES", "0") == "1"
ENABLED = os.getenv("CUSTOM_PIPELINE_ENABLED", "0") == "1"

async def run_custom(file_path: str) -> Dict[str, Any]:
    source = "custom_features"
    if MOCK or not ENABLED:
        import asyncio
        await asyncio.sleep(1.6)
        return {
            "source": source, "ok": True, "mode": "mock",
            "results": [{
                "title": "Mock Melody Match",
                "artist": "—",
                "confidence": 0.42,
                "url": "",
                "preview": "",
                "image": ""
            }]
        }

    # Se abiliterai davvero la pipeline, qui invochi la tua funzione reale:
    # feats = extract_features(file_path)  # es. dal modulo audio_features.py
    # embedding = embed(feats)
    # matches = search_knn(embedding)
    # return {...}
    return {
        "source": source,
        "ok": False,
        "error": "Custom pipeline non attivata (set CUSTOM_PIPELINE_ENABLED=1)"
    }