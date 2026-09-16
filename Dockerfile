# Wioos Witness — production container for Railway
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg: WAV -> OGG/Opus for Telegram voice notes
# libcairo2: SVG -> PNG preview (cairosvg)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Models are downloaded at container START (see app.main) into MODEL_DIR.
# Mount a Railway volume at /data so models survive deploys/restarts.
ENV MODEL_DIR=/data/models \
    TMP_VOICE_DIR=/tmp/voice \
    TMP_SVG_DIR=/tmp/svg

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=5 \
    CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+__import__('os').environ.get('PORT','8080')+'/health',timeout=4).status==200 else 1)" || exit 1

CMD ["python", "-m", "app.main"]
