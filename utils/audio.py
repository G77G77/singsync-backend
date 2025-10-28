import os
import tempfile
import subprocess
from fastapi import UploadFile

async def ensure_wav_16k_mono(upload: UploadFile) -> str:
    """
    Prende qualunque input (m4a/mp3/wav) e produce un WAV PCM 16k mono tramite ffmpeg.
    Ritorna il percorso del file normalizzato.
    """
    # salva input
    src_fd, src_path = tempfile.mkstemp(suffix=os.path.splitext(upload.filename or "")[1] or ".bin")
    with os.fdopen(src_fd, "wb") as f:
        f.write(await upload.read())

    # destinazione
    dst_fd, dst_path = tempfile.mkstemp(suffix=".wav")
    os.close(dst_fd)

    # ffmpeg -y -i in -ac 1 -ar 16000 -f wav out
    cmd = [
        "ffmpeg", "-y",
        "-i", src_path,
        "-ac", "1",
        "-ar", "16000",
        "-f", "wav",
        dst_path
    ]
    # esegui
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0 or not os.path.exists(dst_path):
        raise RuntimeError(f"ffmpeg conversion error: {proc.stderr.decode(errors='ignore')[:300]}")
    return dst_path