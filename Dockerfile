# Immagine base già pronta con torch e ffmpeg

FROM ghcr.io/huggingface/transformers-pytorch-cpu:latest

WORKDIR /app
COPY . .

# Installa solo le nostre dipendenze extra
RUN pip install --no-cache-dir fastapi==0.110.0 \
    uvicorn==0.27.1 \
    python-multipart==0.0.6 \
    requests==2.31.0 \
    faster-whisper==1.0.3 \
    python-dotenv==1.0.1 \
    numpy==1.26.4 \
    pydantic==2.7.1 \
    pydub

ENV PORT=8080
EXPOSE 8080

CMD ["bash", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
