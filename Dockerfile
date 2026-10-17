# HoodieMap: the built frontend served by the FastAPI app. See docs/deploy.md.
FROM node:20.18-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
COPY migrations/ migrations/
COPY fixtures/ fixtures/
COPY config.yaml ./
COPY --from=frontend /build/frontend/dist frontend/dist
# data/ (photos) and .cache/ (OSM + geocoding) are relative to the working directory: mount volumes there.
RUN useradd --create-home --uid 1000 hoodiemap && mkdir -p data .cache && chown hoodiemap data .cache
USER hoodiemap
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
# One worker: the Nominatim throttle (1 request/s) is per process.
CMD ["uvicorn", "--app-dir", "src", "api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
