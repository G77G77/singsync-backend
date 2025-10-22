import librosa
import numpy as np
import crepe
import tempfile
import os
from pydub import AudioSegment

def convert_to_wav(input_path):
    """Converte qualsiasi file audio in .wav (16kHz mono)."""
    try:
        audio = AudioSegment.from_file(input_path)
        wav_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(wav_path, format="wav")
        return wav_path
    except Exception as e:
        print(f"⚠️ Errore conversione WAV: {e}")
        return input_path


def extract_features(audio_path: str):
    """
    Estrae feature musicali di base da un file audio:
      - Tempo (BPM)
      - Key (tonalità)
      - MFCC
      - Chroma (armonia)
      - Pitch medio tramite CREPE
    """
    try:
        wav_path = convert_to_wav(audio_path)
        y, sr = librosa.load(wav_path, sr=16000)

        # 1️⃣ Tempo (BPM)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

        # 2️⃣ Tonalità
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = np.mean(chroma, axis=1)
        key_index = np.argmax(chroma_mean)
        keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        key_estimate = keys[key_index % 12]

        # 3️⃣ MFCC (caratteristiche timbriche)
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_mean = np.mean(mfcc, axis=1).tolist()

        # 4️⃣ Pitch tracking (CREPE)
        pitch_mean = None
        pitch_std = None
        try:
            _, frequency, confidence, _ = crepe.predict(wav_path, sr, viterbi=True, step_size=10)
            valid = confidence > 0.8
            if np.any(valid):
                pitch_mean = float(np.mean(frequency[valid]))
                pitch_std = float(np.std(frequency[valid]))
        except Exception as e:
            print(f"⚠️ CREPE non riuscito: {e}")

        features = {
            "tempo": float(tempo),
            "key": key_estimate,
            "mfcc_mean": mfcc_mean,
            "pitch_mean": pitch_mean,
            "pitch_std": pitch_std,
            "chroma_mean": chroma_mean.tolist()
        }

        os.remove(wav_path)
        print(f"🎵 Feature estratte con successo: {features}")
        return features

    except Exception as e:
        print(f"❌ Errore estrazione feature: {e}")
        return {"error": str(e)}
