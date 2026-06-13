FROM python:3.11-slim
WORKDIR /app
COPY retrieval-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY retrieval-api/ .
CMD ["uvicorn", "app.retrieval_api:app", "--host", "0.0.0.0", "--port", "8000"]
