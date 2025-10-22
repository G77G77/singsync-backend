🎵 SingSync Backend (v3.0)

SingSync è un backend FastAPI per il riconoscimento musicale intelligente.
Combina Whisper (OpenAI API), AudD, Genius API e feature extraction Librosa per riconoscere canzoni da audio cantato o registrato.
Ottimizzato per Render con CPU e costi ridotti (~10–13 $/mese).


---

🚀 Funzionalità principali

Modulo	Descrizione	Stato

🎙️ Whisper API	Trascrizione automatica parlato/cantato → testo	✅ Attivo
🎧 AudD API	Fingerprint e ricerca musicale (brani originali)	✅ Attivo
🧠 Genius API	Ricerca brano da testo e recupero lyrics	✅ Attivo
🎼 Librosa Features	Analisi melodia, tempo, armonia (fase 1)	🧪 In test
⚡ Fusion Engine	Matching Whisper + AudD + Genius con confidenza	✅ Attivo



---

🧩 Architettura

AUDIO (cantato o registrato)
│
├─► 1️⃣ Whisper API → trascrizione testo
├─► 2️⃣ AudD → fingerprint / Spotify metadata
├─► 3️⃣ Genius → ricerca brano da testo
├─► 4️⃣ Librosa → feature extraction (pitch, MFCC, ritmo)
└─► 5️⃣ Fusione → ranking finale + output a frontend
