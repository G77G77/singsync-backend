# Base ufficiale PyTorch CPU stabile (2.0.1)
FROM pytorch/pytorch:2.0.1-cpu

# Installa ffmpeg per Whisper e pulisci cache
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Imposta directory di lavoro
WORKDIR /app
COPY . .

# Installa dipendenze
RUN pip install --no-cache-dir fastapi==0.110.0 \
    uvicorn==0.27.1 \
    python-multipart==0.0.6 \
    requests==2.31.0 \
    faster-whisper==1.0.3 \
    python-dotenv==1.0.1 \
    numpy==1.26.4 \
    pydantic==2.7.1 \
    pydub

# Porta dinamica per Railway
ENV PORT=8080
EXPOSE 8080

# Avvio del server FastAPI
CMD ["bash", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
