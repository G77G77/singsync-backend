import numpy as np
import librosa
import json
import traceback
import os

def extract_features(file_path: str):
    """
    Estrae feature musicali di base da un file audio.
    Usa Librosa + (opzionalmente) CREPE se disponibile.
    Restituisce un dizionario di feature numeriche.
    """
    try:
        # --- Carica audio ---
        y, sr = librosa.load(file_path, sr=16000, mono=True)
        dur = librosa.get_duration(y=y, sr=sr)
        if dur < 0.5:
            return {"error": "clip troppo breve"}

        feats = {"sr": sr, "duration": round(dur, 2)}

        # --- Tempo (BPM) ---
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        feats["tempo"] = float(tempo)

        # --- Energia media ---
        feats["energy"] = float(np.mean(librosa.feature.rms(y=y)))

        # --- Chroma ---
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        feats["chroma_mean"] = float(np.mean(chroma))
        feats["chroma_var"] = float(np.var(chroma))

        # --- MFCC ---
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        feats["mfcc_mean"] = float(np.mean(mfcc))
        feats["mfcc_std"] = float(np.std(mfcc))
        feats["mfcc_0"] = float(np.mean(mfcc[0]))

        # --- Tonalità approssimata ---
        chroma_cens = librosa.feature.chroma_cens(y=y, sr=sr)
        tonal_centroid = np.mean(chroma_cens, axis=1)
        feats["tonal_centroid_mean"] = float(np.mean(tonal_centroid))

        # --- Pitch classico (YIN) ---
        try:
            pitch = librosa.yin(y, fmin=50, fmax=1000)
            feats["pitch_mean_yin"] = float(np.mean(pitch))
            feats["pitch_std_yin"] = float(np.std(pitch))
        except Exception:
            feats["pitch_mean_yin"] = None

        # --- CREPE pitch (opzionale) ---
        try:
            import crepe
            f0, confidence, _ = crepe.predict(y, sr, viterbi=True, verbose=0)
            feats["pitch_crepe_mean"] = float(np.mean(f0))
            feats["pitch_crepe_conf"] = float(np.mean(confidence))
            feats["crepe_used"] = True
        except Exception:
            feats["crepe_used"] = False

        # --- Spettro ---
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        feats["spectral_centroid_mean"] = float(np.mean(centroid))
        feats["spectral_centroid_var"] = float(np.var(centroid))

        bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
        feats["bandwidth_mean"] = float(np.mean(bandwidth))

        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        feats["rolloff_mean"] = float(np.mean(rolloff))

        # --- ZCR (Zero Crossing Rate) ---
        zcr = librosa.feature.zero_crossing_rate(y)
        feats["zcr_mean"] = float(np.mean(zcr))

        # --- Normalizzazione e output finale ---
        feats = {k: (float(v) if isinstance(v, (np.floating, np.float32, np.float64)) else v)
                 for k, v in feats.items()}

        return feats

    except Exception as e:
        print("❌ Errore estrazione feature:", e)
        traceback.print_exc()
        return {"error": str(e)}
