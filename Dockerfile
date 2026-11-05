FROM node:22-alpine AS ui
WORKDIR /src
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY requirements-container.txt ./
RUN pip install --no-cache-dir -r requirements-container.txt
COPY storage.py queue_store.py local_api.py job_runner.py import_drive.py ingest.py web_proxy.py container_start.py migration_restore.py ./
COPY --from=ui /src/dist ./frontend/dist
ENV WEFIX_DB_PATH=/app/data/wefix_prices.sqlite3 WEFIX_QUEUE_ENABLED=1 WEFIX_API_BIND=0.0.0.0
EXPOSE 8000 8766
CMD ["python", "container_start.py"]
