# Nutq 2 — self-hosted phoneme pronunciation scorer.
# CPU-only, offline at runtime (model + nltk data baked into the image).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NLTK_DATA=/opt/nltk_data \
    # keep CPU usage bounded on a small shared box
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    NUMEXPR_NUM_THREADS=2

# ffmpeg decodes the browser recording (webm/ogg/mp4) → 16k mono wav
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch first (no CUDA → far smaller image)
RUN pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Preload G2P (nltk) data — both old and new tagger resource names
RUN python -m nltk.downloader -d /opt/nltk_data \
        averaged_perceptron_tagger averaged_perceptron_tagger_eng cmudict

COPY scorer.py server.py ./

# Bake the allosaurus model into the image so runtime needs no network
RUN python -c "from allosaurus.app import read_recognizer; read_recognizer()"

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').getcode()==200 else 1)"

CMD ["python", "server.py"]
