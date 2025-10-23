import numpy as np
import librosa

# Krumhansl major/minor templates (12-D)
_K_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_K_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_NOTES   = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]

def _estimate_key(chroma_mean: np.ndarray):
    """Correla il cromagramma medio con i profili maggiori/minori trasposti."""
    if chroma_mean.ndim != 1 or chroma_mean.size != 12:
        return {"key": None, "scale": None, "confidence": 0.0}

    # normalizza
    cm = chroma_mean / (np.linalg.norm(chroma_mean) + 1e-8)
    best = None
    best_corr = -1e9
    best_scale = None
    for shift in range(12):
        # ruota i template
        maj = np.roll(_K_MAJOR, shift)
        min_ = np.roll(_K_MINOR, shift)
        maj = maj / (np.linalg.norm(maj) + 1e-8)
        min_ = min_ / (np.linalg.norm(min_) + 1e-8)

        corr_maj = float(np.dot(cm, maj))
        corr_min = float(np.dot(cm, min_))
        if corr_maj > best_corr:
            best_corr = corr_maj
            best = _NOTES[shift]
            best_scale = "major"
        if corr_min > best_corr:
            best_corr = corr_min
            best = _NOTES[shift]
            best_scale = "minor"
    conf = float(max(0.0, min(1.0, (best_corr + 1) / 2)))  # mappa [-1,1] → [0,1]
    return {"key": best, "scale": best_scale, "confidence": conf}

def extract_features(path: str) -> dict:
    """
    CPU-only, robusto:
      - carica mono a 22.05 kHz
      - taglia a max 30s per velocità
      - tempo (BPM), cromagramma, key, pitch (YIN), centroid, bandwidth, rolloff, rms
    """
    sr = 22050
    y, sr = librosa.load(path, sr=sr, mono=True, duration=30.0)

    # Sicurezza se silenzio
    if y is None or y.size == 0:
        return {"duration": 0.0, "error": "audio vuoto"}

    duration = float(len(y) / sr)

    # Onset/tempo
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
    tempo = float(tempo)

    # Chroma (CQT)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)
    key_info = _estimate_key(chroma_mean)

    # Pitch (YIN) — robusto su voce/canto monofonico
    try:
        f0 = librosa.yin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'), sr=sr)
        # rimuovi outlier e zero/NaN
        f0 = f0[np.isfinite(f0)]
        f0 = f0[f0 > 0]
        if f0.size > 0:
            f0_hz_mean = float(np.median(f0))
            f0_midi = float(librosa.hz_to_midi(f0_hz_mean))
        else:
            f0_hz_mean = 0.0
            f0_midi = 0.0
    except Exception:
        f0_hz_mean, f0_midi = 0.0, 0.0

    # Spettrali
    centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)))
    rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))
    rms = float(np.mean(librosa.feature.rms(y=y)))

    return {
        "duration": duration,
        "tempo_bpm": tempo,
        "key": key_info["key"],
        "scale": key_info["scale"],
        "key_confidence": key_info["confidence"],
        "pitch_hz": f0_hz_mean,
        "pitch_midi": f0_midi,
        "spectral_centroid": centroid,
        "spectral_bandwidth": bandwidth,
        "spectral_rolloff": rolloff,
        "rms": rms,
        "chroma_mean": chroma_mean.tolist(),  # (12,) per possibili passi successivi
    }