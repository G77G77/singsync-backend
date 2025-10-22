# audio_features.py
import numpy as np
import librosa

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F',
              'F#', 'G', 'G#', 'A', 'A#', 'B']

def hz_to_note_name(hz: float) -> dict:
    """Converte Hz in nota + MIDI (A4=440). Ritorna {} se non valido."""
    if not hz or np.isnan(hz) or hz <= 0:
        return {}
    midi = 69 + 12 * np.log2(hz / 440.0)
    midi_rounded = int(np.round(midi))
    note_index = midi_rounded % 12
    octave = midi_rounded // 12 - 1
    return {
        "pitch_hz": float(hz),
        "pitch_midi": midi_rounded,
        "pitch_note": f"{NOTE_NAMES[note_index]}{octave}"
    }

def safe_mean(x):
    try:
        v = np.nanmean(x)
        return float(v) if np.isfinite(v) else None
    except Exception:
        return None

def extract_features(path: str, target_sr: int = 22050) -> dict:
    """Estrazione feature audio (CPU-friendly) per la Fase 1."""
    y, sr = librosa.load(path, sr=target_sr, mono=True)
    duration = float(librosa.get_duration(y=y, sr=sr))

    out = {
        "sr": sr,
        "duration_sec": duration,
        "tempo_bpm": None,
        "beats_count": None,
        "pitch": {},              # {pitch_hz, pitch_midi, pitch_note}
        "chroma_means": [],       # 12 valori (C..B)
        "mfcc_means": [],         # 13 valori
        "spectral_centroid_hz": None,
        "spectral_rolloff_hz": None,
        "zcr": None,
        "rms": None,
    }

    # 1) Tempo/Beat
    try:
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        out["tempo_bpm"] = float(tempo)
        out["beats_count"] = int(len(beat_frames))
    except Exception:
        pass

    # 2) Pitch (robusto: YIN; se fallisce, torna vuoto)
    try:
        # finestra 2048 hop 256 => abbastanza rapido
        f0 = librosa.yin(y, fmin=librosa.note_to_hz('C2'),
                         fmax=librosa.note_to_hz('C7'),
                         sr=sr, frame_length=2048, hop_length=256)
        # prendo la mediana ignorando NaN
        f0_med = np.nanmedian(f0)
        if np.isfinite(f0_med) and f0_med > 0:
            out["pitch"] = hz_to_note_name(float(f0_med))
    except Exception:
        pass

    # 3) Chroma CQT → media canali
    try:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        out["chroma_means"] = [float(v) for v in np.nanmean(chroma, axis=1).tolist()]
    except Exception:
        pass

    # 4) MFCC (13)
    try:
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        out["mfcc_means"] = [float(v) for v in np.nanmean(mfcc, axis=1).tolist()]
    except Exception:
        pass

    # 5) Spettrali + energia
    try:
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)
        zcr = librosa.feature.zero_crossing_rate(y)
        rms = librosa.feature.rms(y=y)

        out["spectral_centroid_hz"] = safe_mean(librosa.hz_to_mel(centroid))  # opzionale: mel
        # se vuoi in Hz direttamente, usa float(np.nanmean(centroid))
        out["spectral_centroid_hz"] = float(np.nanmean(centroid)) if np.isfinite(np.nanmean(centroid)) else None
        out["spectral_rolloff_hz"]  = float(np.nanmean(rolloff))  if np.isfinite(np.nanmean(rolloff))  else None
        out["zcr"] = float(np.nanmean(zcr)) if np.isfinite(np.nanmean(zcr)) else None
        out["rms"] = float(np.nanmean(rms)) if np.isfinite(np.nanmean(rms)) else None
    except Exception:
        pass

    return out
