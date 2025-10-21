# Dockerfile - SingSync (Render)
FROM python:3.10-slim

# 1) Sistema + ffmpeg (necessario per faster-whisper/pydub)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# 2) Torch CPU precompilato + dipendenze applicative
#    (torch/torchaudio via index CPU ufficiale per evitare build lunghe e instabili)
RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
      torch==2.1.2+cpu \
      torchaudio==2.1.2+cpu \
      --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir \
      fastapi==0.110.0 \
      uvicorn==0.27.1 \
      python-multipart==0.0.6 \
      requests==2.31.0 \
      faster-whisper==1.0.3 \
      python-dotenv==1.0.1 \
      numpy==1.26.4 \
      pydantic==2.7.1 \
      pydub

# 3) Porta dinamica su Render (verrà passata anche come $PORT)
ENV PORT=8080
EXPOSE 8080

# 4) Avvio server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
