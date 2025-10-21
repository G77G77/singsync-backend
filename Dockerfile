# Base: immagine ufficiale PyTorch con CPU
FROM pytorch/pytorch:2.1.2-cpu

# Aggiorna sistema e installa ffmpeg (per Whisper)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Installa le dipendenze
RUN pip install --no-cache-dir fastapi==0.110.0 \
    uvicorn==0.27.1 \
    python-multipart==0.0.6 \
    requests==2.31.0 \
    faster-whisper==1.0.3 \
    python-dotenv==1.0.1 \
    numpy==1.26.4 \
    pydantic==2.7.1 \
    pydub

# Espone la porta dinamica (Railway)
ENV PORT=8080
EXPOSE 8080

# Comando di avvio
CMD ["bash", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
