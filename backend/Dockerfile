FROM python:3.12-slim

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1 HF_HOME=/models

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt \
    && python -c "import nltk; [nltk.download(p) for p in ('stopwords','wordnet','omw-1.4')]"

COPY backend/ .
COPY frontend/dist /app/frontend/dist

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
