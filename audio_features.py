import numpy as np
import librosa

def extract_features(file_path: str):
    """
    Estrazione feature leggere CPU-only:
    - SR 16k mono
    - RMS (energia)
    - Chroma CQT
    - Beat tempo
    """
    y, sr = librosa.load(file_path, sr=16000, mono=True)
    y = librosa.util.normalize(y)

    rms = librosa.feature.rms(y=y).mean().item()
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1).tolist()

    return {
        "sr": sr,
        "duration_sec": float(len(y) / sr),
        "rms": float(rms),
        "tempo_bpm": float(tempo),
        "chroma_mean": chroma_mean,
    }