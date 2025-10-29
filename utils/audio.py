import os
import tempfile
import subprocess
from fastapi import UploadFile

FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")

async def ensure_wav_16k_mono(uploaded: UploadFile) -> str:
    """
    Salva l'UploadFile su disco e converte (se serve) in WAV PCM s16le 16k mono usando ffmpeg.
    Ritorna il path al file WAV normalizzato.
    """
    # Salva input grezzo
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.filename or "")[-1] or ".bin") as tmp_in:
        raw = await uploaded.read()
        tmp_in.write(raw)
        in_path = tmp_in.name

    # Output WAV 16k mono
    out_fd, out_path = tempfile.mkstemp(suffix=".wav")
    os.close(out_fd)

    cmd = [
        FFMPEG_BIN, "-y",
        "-i", in_path,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-sample_fmt", "s16",
        out_path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        # Se fallisce, riprova forcing format
        raise RuntimeError(f"ffmpeg conversion failed: {e.stderr.decode(errors='ignore')[:400]}")
    finally:
        # pulizia input sorgente
        try:
            os.remove(in_path)
        except Exception:
            pass

    return out_path