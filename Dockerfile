# Dockerfile - SingSync Render fix
FROM python:3.10-slim

# Installa sistema e ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git build-essential libsndfile1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Aggiorna pip e installa pacchetti precompilati (senza build Rust)
RUN pip install --upgrade pip wheel setuptools && \
    pip install --no-cache-dir torch==2.1.2+cpu torchaudio==2.1.2+cpu \
      --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir fastapi==0.110.0 uvicorn==0.27.1 python-multipart==0.0.6 \
      requests==2.31.0 python-dotenv==1.0.1 numpy==1.26.4 pydantic==2.7.1 pydub && \
    pip install --no-cache-dir "faster-whisper==1.0.3" --prefer-binary

# Variabili e porta
ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
