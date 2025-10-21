FROM python:3.10-slim


# Installa ffmpeg (serve per whisper / audio)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Imposta la directory di lavoro
WORKDIR /app
COPY . .

# Installa dipendenze
RUN pip install --no-cache-dir -r requirements.txt

# Usa la variabile PORT di Railway
ENV PORT=8080

# Espone la porta
EXPOSE 8080

# Avvia FastAPI con uvicorn
CMD ["bash", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
