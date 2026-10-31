FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 KOKORO_DIR=/models/kokoro
# espeak-ng: Kokoro's fallback pronunciation for words its dictionary doesn't know.
RUN apt-get update && apt-get install -y --no-install-recommends espeak-ng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
# CPU-only torch keeps the image small; an 82M-parameter model is fast enough on CPU.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

# Kokoro-82M weights + voices, baked into the image at a pinned revision (about 330 MB).
ARG KOKORO_REVISION=f3ff3571791e39611d31c381e3a41a3af07b4987
ARG KOKORO_VOICES="af_heart af_bella af_nicole af_sarah am_michael am_adam bf_emma bm_george"
COPY fetch_model.py .
RUN python fetch_model.py

# Everything is local from here on: never reach out to Hugging Face at runtime.
ENV HF_HUB_OFFLINE=1
COPY app.py .
EXPOSE 8880
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8880"]
