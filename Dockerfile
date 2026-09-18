# BrandShield AI on Hugging Face Spaces (Docker SDK)
# Build the dashboard, then run FastAPI on the port Spaces expects (7860).

# ---------- 1. build the React dashboard ----------
FROM node:20-slim AS ui
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. the application ----------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/tmp/hf \
    PORT=7860

WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt \
    && python -c "import nltk; [nltk.download(p, quiet=True) for p in ('stopwords','wordnet','omw-1.4')]"

# bake the sentiment model into the image so the Space starts fast
RUN python -c "from transformers import pipeline; pipeline('text-classification', model='tabularisai/multilingual-sentiment-analysis', top_k=None)"

COPY backend/ .
COPY --from=ui /ui/dist /app/frontend/dist
COPY deploy/huggingface/start.sh /start.sh

# Spaces runs as a non-root user; everything writable must be world-writable
RUN chmod +x /start.sh && mkdir -p /tmp/data /opt/hf && chmod -R 777 /tmp/data /opt/hf

EXPOSE 7860
CMD ["/start.sh"]
