# ✅ Base leggera con Python 3.10 e FFmpeg
FROM python:3.10-slim

# Installa FFmpeg (per la conversione audio)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Imposta la cartella di lavoro
WORKDIR /app

# Copia i file del progetto
COPY . .

# Installa le dipendenze
RUN pip install --no-cache-dir -r requirements.txt

# Espone la porta su cui FastAPI sarà in ascolto
EXPOSE 10000

# Avvia il server (Render usa PORT come variabile automatica)
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
