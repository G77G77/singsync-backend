# Usa Python slim
FROM python:3.10-slim

# Arg per installazione custom deps
ARG INSTALL_CUSTOM_DEPS=0

# Imposta working dir
WORKDIR /app

# Copia file requirements e installa dipendenze
COPY requirements.txt .
COPY requirements-custom.txt .

# Dipendenze di sistema necessarie
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libsndfile1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Installa le dipendenze Python base
RUN pip install --no-cache-dir -r requirements.txt

# Installa (opzionale) pacchetti pesanti solo se specificato
RUN if [ "$INSTALL_CUSTOM_DEPS" = "1" ]; then \
        pip install --no-cache-dir -r requirements-custom.txt; \
    else \
        echo "⚠️  Skipping heavy deps (tensorflow, crepe, openl3)"; \
    fi

# Copia tutto il progetto
COPY . .

# Variabili d'ambiente
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Espone porta
EXPOSE 8080

# Comando di avvio
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]