@router.get("/identify_all")
async def identify_all(token: str):
    """Esegue tutte le pipeline (whisper, acrcloud, custom)."""
    if token not in UPLOADS:
        raise HTTPException(status_code=400, detail="Token non valido")

    path = UPLOADS[token]

    tasks = []

    # ✅ ACRCloud
    if os.getenv("ENABLE_ACRCLOUD", "1") == "1":
        tasks.append(run_acrcloud(token, path))

    # ✅ Whisper + Genius
    if os.getenv("ENABLE_WHISPER_GENIUS", "1") == "1":
        tasks.append(run_whisper_genius(token, path))

    # ✅ Custom
    if os.getenv("ENABLE_CUSTOM", "0") == "1":
        tasks.append(run_custom(token, path))

    # Attende tutti i risultati
    results = await asyncio.gather(*tasks, return_exceptions=True)
    parsed = []
    for r in results:
        if isinstance(r, Exception):
            parsed.append({
                "source": "internal",
                "ok": False,
                "error": str(r),
                "elapsed_sec": 0
            })
        else:
            parsed.append(r)

    return {"ok": True, "results": parsed}