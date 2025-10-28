# ------------------------------
# SingSync Backend - Dockerfile
# Versione: 4.0 - Ottimizzata per Render
# ------------------------------

# Base image leggera con Python 3.10 (compatibile TensorFlow CPU)
FROM python:3.10-slim

# Imposta la working directory
WORKDIR /app

# Evita output bufferizzato
ENV PYTHONUNBUFFERED=1

# Installa dipendenze di sistema essenziali per audio (librosa, soundfile, ffmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libsndfile1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copia i file requirements e installa le dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il progetto nel container
COPY . .

# Espone la porta predefinita per Render (8080)
EXPOSE 8080

# Comando di avvio (Uvicorn con FastAPI)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]