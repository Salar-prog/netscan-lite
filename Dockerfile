# Stage 1: Build dashboard
FROM node:20-slim AS dashboard-builder

WORKDIR /app/netscan_lite/dashboard
COPY netscan_lite/dashboard/package.json netscan_lite/dashboard/package-lock.json ./
RUN npm ci
COPY netscan_lite/dashboard/ ./
RUN npm run build

# Stage 2: Build Python package
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends nmap && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY netscan_lite/__init__.py netscan_lite/__init__.py
RUN pip install --no-cache-dir -e ".[xlsx]" 2>/dev/null || pip install --no-cache-dir .

COPY . .
RUN pip install --no-cache-dir -e ".[xlsx]"

# Stage 3: Final runtime image
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends nmap curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/ns-lite /usr/local/bin/ns-lite
COPY --from=dashboard-builder /app/netscan_lite/static /usr/local/lib/python3.12/site-packages/netscan_lite/static

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["ns-lite", "serve", "--host", "0.0.0.0"]
