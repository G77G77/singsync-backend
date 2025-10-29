import os
from typing import Dict, Any

def _custom_disabled() -> bool:
    return os.getenv("ENABLE_CUSTOM", "0") != "1"

def run_custom(audio_path: str) -> Dict[str, Any]:
    """
    Pipeline custom:
      - Lazy import deps pesanti (tensorflow, crepe, openl3)
      - Estrae pitch + cromagramma + tempo + embedding
      - Ritorna una "card" informativa (senza matching DB in questa fase)
    """
    if _custom_disabled():
        return {"source": "custom", "ok": False, "disabled": True}

    # Lazy import
    missing = []
    try:
        import numpy as np
        import librosa
    except Exception:
        return {"source": "custom", "ok": False, "error": "deps_missing: numpy/librosa"}

    try:
        import crepe  # noqa
    except Exception:
        missing.append("crepe")

    try:
        import tensorflow as tf  # noqa
    except Exception:
        missing.append("tensorflow")

    try:
        import openl3
    except Exception:
        missing.append("openl3")

    if missing:
        return {"source": "custom", "ok": False, "error": f"deps_missing: {','.join(missing)}"}

    # Se le deps ci sono, procedi
    import crepe
    import openl3

    # Carica audio
    y, sr = librosa.load(audio_path, sr=16000, mono=True)
    y = librosa.util.normalize(y)

    # Pitch con CREPE (model capacity 'tiny' per velocità)
    # CREPE vuole sr=16000 float32
    import numpy as _np
    audio_f32 = _np.asarray(y, dtype=_np.float32)
    time_f, frequency, confidence, activation = crepe.predict(
        audio_f32, sr, step_size=20, model_capacity='tiny', viterbi=True
    )
    # pitch median (Hz) considerando confidenza > 0.5
    valid = frequency[confidence > 0.5]
    pitch_hz = float(_np.median(valid)) if valid.size else 0.0

    # Beat/tempo + chroma
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1).tolist()

    # Embedding OpenL3 (modello audio, content_type music, 512 dim)
    emb, ts = openl3.get_audio_embedding(
        y, sr, input_repr="mel128", content_type="music", embedding_size=512, center=True, hop_size=0.5
    )
    # media embedding
    emb_mean = emb.mean(axis=0).tolist()

    return {
        "source": "custom",
        "ok": True,
        "results": [
            {
                "title": "Custom Analysis",
                "artist": "",
                "url": "",
                "preview": "",
                "image": "",
                "confidence": 0.4,
                "features": {
                    "sr": sr,
                    "duration_sec": float(len(y)/sr),
                    "pitch_hz": pitch_hz,
                    "tempo_bpm": float(tempo),
                    "chroma_mean": chroma_mean,
                    "embedding_size": len(emb_mean)
                }
            }
        ]
    }