# Usa immagine base leggera e stabile
FROM python:3.10-slim

# Installa ffmpeg e dipendenze di sistema
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Imposta directory di lavoro
WORKDIR /app
COPY . .

# Installa le dipendenze Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir torch==2.1.2+cpu \
    torchaudio==2.1.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir fastapi==0.110.0 \
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

# Avvia il server
CMD ["bash", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
