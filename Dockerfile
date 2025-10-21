# Dockerfile - SingSync stable Render build (no Rust build)
FROM python:3.10-slim

# 1️⃣ Installa sistema e ffmpeg (senza build tools Rust)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 git build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# 2️⃣ Aggiorna pip e forza installazione pacchetti precompilati
RUN pip install --upgrade pip wheel setuptools

# 3️⃣ Installa pacchetti principali
RUN pip install --no-cache-dir torch==2.1.2+cpu torchaudio==2.1.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir fastapi==0.110.0 uvicorn==0.27.1 \
    python-multipart==0.0.6 requests==2.31.0 python-dotenv==1.0.1 \
    numpy==1.26.4 pydub

# 4️⃣ Installa pydantic e faster-whisper come binari
RUN pip install --no-cache-dir "pydantic==2.7.1" --prefer-binary && \
    pip install --no-cache-dir "faster-whisper==1.0.3" --prefer-binary

# 5️⃣ Espone la porta dinamica e avvia
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
