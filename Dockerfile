FROM python:3.10-slim

# Dipendenze sistema
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Librerie Python
RUN pip install --no-cache-dir fastapi==0.110.0 uvicorn==0.27.1 python-multipart==0.0.6 requests==2.31.0 \
    faster-whisper==1.0.3 torch==2.1.2 torchaudio==2.1.2 python-dotenv==1.0.1 numpy==1.26.4 pydantic==2.7.1 pydub

EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
