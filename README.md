---

📘 SingSync Backend – Versione 4.0

🧩 Panoramica

Il backend di SingSync gestisce l’intera pipeline di riconoscimento musicale, da audio grezzo a identificazione brano, tramite un sistema ibrido basato su:

🎧 ARCCloud API (riconoscimento commerciale)

🧠 OpenAI Whisper + Genius API

🎵 Librosa + CREPE + FAISS (feature extraction e audio matching personalizzato)

⚡ SSE (Server-Sent Events) per invio risultati progressivi in streaming



---

⚙️ Stack Tecnologico

Tecnologia	Scopo

FastAPI	backend principale e gestione API
Uvicorn	server ASGI leggero
TensorFlow CPU + CREPE	analisi tono e pitch
Librosa / SciPy / SoundFile	feature extraction musicale
FAISS (CPU)	ricerca vettoriale veloce per similarità audio
Render	hosting e deploy automatico
Docker	ambiente di esecuzione isolato e riproducibile



---

🧱 Struttura del progetto

singsync-backend/
│
├── app.py                   # Entry point FastAPI
├── requirements.txt         # Dipendenze Python
├── Dockerfile               # Build container Render
├── .render.yaml             # Configurazione deploy Render
│
├── routers/
│   └── main_router.py       # Endpoint /upload_audio, /identify_stream, /identify_all
│
├── pipelines/
│   ├── pipeline_acrcloud.py
│   ├── pipeline_whisper_genius.py
│   ├── pipeline_custom.py
│
├── utils/
│   ├── sse.py               # Gestione eventi Server-Sent Events
│   ├── audio.py             # Normalizzazione, conversione WAV 16k
│   └── __init__.py
│
└── README.md                # Documentazione del progetto


---

🧠 Endpoint Principali

Endpoint	Metodo	Descrizione

/health	GET	Stato del servizio e API keys attive
/upload_audio	POST	Riceve file audio (m4a/wav) → ritorna un token
/identify_stream	GET	Restituisce 3 risultati in streaming (ARCCloud, Whisper, Custom)
/identify_all	POST	Restituisce tutti i risultati in un unico JSON



---