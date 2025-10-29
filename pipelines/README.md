# SingSync Pipelines Overview

### Active Modules
- **ACRCloud** — riconoscimento musicale da audio
- **Whisper + Genius** — trascrizione + ricerca testuale
- **Custom (CREPE/OpenL3)** — feature extraction locale

### Feature Flags (ENV)
| Variabile | Descrizione |
|------------|-------------|
| `ENABLE_ACRCLOUD` | Abilita la pipeline ACRCloud |
| `ENABLE_WHISPER_GENIUS` | Usa OpenAI Whisper + Genius API |
| `ENABLE_CUSTOM` | Attiva la pipeline locale CREPE/OpenL3 |
| `INSTALL_CUSTOM_DEPS` | Se = 1 installa TensorFlow & CREPE |
| `SSE_TIMEOUT_SEC` | Timeout massimo per risposte SSE |

### Tipi di risposta SSE
```json
event: acrcloud
data: {"source": "acrcloud", "ok": true, "title": "Billie Jean"}