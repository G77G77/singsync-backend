import os
import numpy as np
import librosa
import traceback

# --- Import "lazy" per TensorFlow / CREPE / OpenL3 ---
try:
    import crepe
except ImportError:
    crepe = None

try:
    import tensorflow as tf
except ImportError:
    tf = None

try:
    import openl3
except ImportError:
    openl3 = None


async def run_custom(audio_path: str):
    """
    Pipeline personalizzata SingSync:
    - Estrae feature audio di base (MFCC, RMS)
    - Se disponibili, usa CREPE e OpenL3 per feature avanzate
    - Restituisce un dizionario compatibile con il frontend
    """
    try:
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        duration = librosa.get_duration(y=y, sr=sr)
        rms = np.mean(librosa.feature.rms(y=y))
        mfcc = np.mean(librosa.feature.mfcc(y=y, sr=sr), axis=1).tolist()

        features = {
            "source": "custom",
            "ok": True,
            "duration": round(duration, 2),
            "rms": round(float(rms), 6),
            "mfcc": mfcc,
            "extra": {}
        }

        # --- CREPE: pitch detection (solo se disponibile) ---
        if crepe is not None:
            try:
                _, frequency, confidence, _ = crepe.predict(y, sr, viterbi=True)
                mean_pitch = float(np.mean(frequency))
                mean_conf = float(np.mean(confidence))
                features["extra"]["crepe_pitch"] = round(mean_pitch, 2)
                features["extra"]["crepe_confidence"] = round(mean_conf, 3)
            except Exception as e:
                features["extra"]["crepe_error"] = str(e)
        else:
            features["extra"]["crepe_status"] = "CREPE non installato (lazy import)"

        # --- OpenL3: embeddings audio (solo se disponibile) ---
        if openl3 is not None:
            try:
                emb, ts = openl3.get_audio_embedding(y, sr, embedding_size=512, content_type="music")
                mean_emb = np.mean(emb, axis=0)[:10].tolist()  # compressione leggera
                features["extra"]["openl3_preview"] = mean_emb
            except Exception as e:
                features["extra"]["openl3_error"] = str(e)
        else:
            features["extra"]["openl3_status"] = "OpenL3 non installato (lazy import)"

        return features

    except Exception as e:
        traceback.print_exc()
        return {
            "source": "custom",
            "ok": False,
            "error": str(e)
        }