# Production Launch Plan — ns-lite v0.2.0

## Context

ns-lite v0.1.0 is an internal IP discovery tool with quarantine logic. It needs production hardening for:
- **Internal dashboard users** (React SPA, LDAP auth)
- **External API consumers** (Terraform, CI, scripts)
- **Deployment**: bare metal preferred, Docker Compose as fallback
- **Infra**: reverse proxy (nginx/Caddy) + monitoring (Prometheus/Grafana) already available

---

## Phase 1: Critical — Unblocks External API Consumers

### Step 1.1: Add CORS middleware

**`netscan_lite/config.py`** — add `CORS_ORIGINS` setting:
```python
CORS_ORIGINS: list[str] = ["*"]
```

**`netscan_lite/main.py`** — add CORS middleware in `create_app()`:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**`netscan_lite/config.py`** — add validation in `validate_production_config()`:
```python
if self.LDAP_ENABLED and self.CORS_ORIGINS == ["*"]:
    warnings.append("CORS_ORIGINS is ['*'] in production — lock this down")
```

**`.env.example`** — add `CORS_ORIGINS=*`

**`tests/test_api.py`** — add `test_cors_headers_present`

---

### Step 1.2: API versioning (`/api/v1/`)

**`netscan_lite/api.py`** line 27:
```python
# Before
router = APIRouter(prefix="/api")
# After
router = APIRouter(prefix="/api/v1")
```

`auth_router` stays at `/token` (no version prefix).

**Test files** — update all `/api/` URLs to `/api/v1/`:
- `tests/test_api.py`: all `client.get("/api/...")` → `/api/v1/...`
- `tests/test_dashboard_api.py`: same pattern

**Docs** — update endpoint examples in `README.md` and `AGENTS.md`.

---

### Step 1.3: Background scan jobs (async)

**New file: `netscan_lite/scanner/jobs.py`**

In-memory job queue with semaphore-limited concurrency:
- `ScanJob` dataclass: job_id, target_ips, group_name, status, result, error, timestamps
- `JobStatus` enum: PENDING, RUNNING, COMPLETED, FAILED
- `create_scan_job()` — creates job, spawns `asyncio.create_task`
- `get_job(job_id)` — returns job or None
- `list_jobs()` — returns all jobs
- `_run_job()` — runs `scan_ips()`, updates job status
- `MAX_CONCURRENT_JOBS = 3` (ponytail: in-memory, add Redis if multi-worker matters)

**`netscan_lite/api.py`** — add new endpoints:

```python
class ScanJobResponse(BaseModel):
    job_id: str
    status: str
    target_count: int
    created_at: str

class ScanJobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[ScanResponse] = None
    error: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

@router.post("/scan/async", response_model=ScanJobResponse, tags=["Scanning"])
async def trigger_scan_async(request: ScanRequest, ...):
    """Start a background scan. Returns job ID for polling."""

@router.get("/scan/{job_id}", response_model=ScanJobStatusResponse, tags=["Scanning"])
async def get_scan_status(job_id: str, ...):
    """Get status and result of a background scan job."""

@router.get("/scan-jobs", tags=["Scanning"])
async def list_scan_jobs(...):
    """List all scan jobs."""
```

Keep existing `POST /scan` as synchronous (backward compat). Add deprecation note.

**`tests/test_api.py`** — add:
- `test_trigger_scan_async_returns_job_id`
- `test_get_scan_status_pending`
- `test_get_scan_status_not_found`

---

## Phase 2: Security Hardening

### Step 2.1: Lock CORS in production

Already covered in Step 1.1 validation.

### Step 2.2: Rate limiter documentation

**`netscan_lite/main.py`** — add comment to `RateLimitMiddleware`:
```python
# ponytail: in-memory per-worker rate limiter. With WORKERS > 1,
# effective limit is max_requests × workers. Use reverse proxy
# rate limiting for global limits in production.
```

No code change needed.

### Step 2.3: Health check enhancement

**`netscan_lite/main.py`** — add `/health/ready`:

```python
@app.get("/health/ready", tags=["System"])
def readiness_check():
    from sqlalchemy import text
    from netscan_lite.db import engine
    import shutil, os

    checks = {}
    ok = True

    # DB check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        ok = False

    # Nmap check
    nmap = shutil.which("nmap")
    checks["nmap"] = "ok" if nmap else "not found"
    if not nmap:
        ok = False

    status_code = 200 if ok else 503
    return {"status": "ready" if ok else "not_ready", "checks": checks}
```

Keep `/health` as lightweight liveness probe (no dependencies). `/health/ready` is the readiness probe.

---

## Phase 3: Operations — Logging & Monitoring

### Step 3.1: Structured logging with request IDs

**New file: `netscan_lite/logging_config.py`**

```python
import logging
import sys
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get("")
        return True


def setup_logging(log_level: str = "info", json_format: bool = False):
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIDFilter())

    if json_format:
        try:
            from pythonjsonlogger.json import JsonFormatter

            formatter = JsonFormatter("%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s")
        except ImportError:
            formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s")
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s")

    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper()))
```

**`netscan_lite/main.py`** — add `RequestIDMiddleware`:
```python
from netscan_lite.logging_config import request_id_var


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request_id_var.set(req_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
```

Add middleware BEFORE `SecurityHeadersMiddleware` (outermost runs first).

**`netscan_lite/main.py`** — call `setup_logging()` in `lifespan()`.

**`netscan_lite/cli.py`** — call `setup_logging()` in `cli()` group.

### Step 3.2: Prometheus metrics

**`pyproject.toml`** — add optional dependency:
```toml
monitoring = ["prometheus-fastapi-instrumentator>=6.1"]
```

**`netscan_lite/config.py`** — add:
```python
ENABLE_METRICS: bool = False
```

**`netscan_lite/main.py`** — conditionally add metrics:
```python
if settings.ENABLE_METRICS:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app)
```

---

## Phase 4: Deployment Packaging

### Step 4.1: systemd service file

**New file: `deploy/ns-lite.service`**
```ini
[Unit]
Description=ns-lite API Server
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=notify
User=ns-lite
Group=ns-lite
WorkingDirectory=/opt/ns-lite
EnvironmentFile=/opt/ns-lite/.env
ExecStart=/usr/local/bin/ns-lite serve --host 0.0.0.0 --port 8000 --workers 4 --log-level info
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
TimeoutStopSec=30

NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/ns-lite/data /home/ns-lite/.ns-lite
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

**New file: `deploy/install.sh`**
```bash
#!/usr/bin/env bash
set -euo pipefail

useradd -r -s /sbin/nologin ns-lite || true
pip install -e ".[xlsx,postgres]"
mkdir -p /opt/ns-lite/data /home/ns-lite/.ns-lite
chown -R ns-lite:ns-lite /opt/ns-lite /home/ns-lite/.ns-lite
cp deploy/ns-lite.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable ns-lite
echo "ns-lite installed. Configure /opt/ns-lite/.env then: systemctl start ns-lite"
```

### Step 4.2: Production Docker Compose

**New file: `docker-compose.prod.yml`**
```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: netscan
      POSTGRES_USER: netscan
      POSTGRES_PASSWORD: ${DB_PASSWORD:?Set DB_PASSWORD in .env}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U netscan"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://netscan:${DB_PASSWORD}@db:5432/netscan
      LDAP_ENABLED: "true"
      LDAP_SERVER: ${LDAP_SERVER}
      LDAP_BIND_DN: ${LDAP_BIND_DN}
      LDAP_BIND_PASSWORD: ${LDAP_BIND_PASSWORD}
      LDAP_SEARCH_BASE: ${LDAP_SEARCH_BASE}
      LDAP_SEARCH_FILTER: ${LDAP_SEARCH_FILTER:-"(sAMAccountName={username})"}
      LDAP_USE_SSL: ${LDAP_USE_SSL:-false}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY:-}
      JWT_EXPIRY_HOURS: ${JWT_EXPIRY_HOURS:-24}
      CORS_ORIGINS: ${CORS_ORIGINS:-*}
      WORKERS: ${WORKERS:-4}
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
    read_only: true
    tmpfs: /tmp
    security_opt:
      - no-new-privileges:true

volumes:
  pgdata:
```

### Step 4.3: Production .env template

**New file: `.env.production`**
```bash
# ns-lite Production Configuration
# Copy to .env and fill in values

DATABASE_URL=postgresql://netscan:CHANGE_ME@localhost:5432/netscan
DB_PASSWORD=CHANGE_ME

LDAP_ENABLED=true
LDAP_SERVER=ldap://your-ldap-server
LDAP_BIND_DN=cn=ns-lite-service,ou=services,dc=example,dc=com
LDAP_BIND_PASSWORD=CHANGE_ME
LDAP_SEARCH_BASE=ou=users,dc=example,dc=com
LDAP_SEARCH_FILTER=(sAMAccountName={username})
LDAP_USE_SSL=false

JWT_SECRET_KEY=CHANGE_ME_TO_RANDOM_64_CHARS
JWT_EXPIRY_HOURS=24

CORS_ORIGINS=https://ns-lite.yourcompany.com

WORKERS=4
DEBUG=false

ENABLE_METRICS=true
```

---

## Phase 5: Test Updates & CI

### Step 5.1: Update all test URLs for API versioning

**Files:** `tests/test_api.py`, `tests/test_dashboard_api.py`
- Replace all `/api/` with `/api/v1/` in HTTP calls

### Step 5.2: Add tests for new features

**`tests/test_api.py`** — add:
- `test_cors_headers_present`
- `test_health_ready_ok`
- `test_trigger_scan_async_returns_job_id`
- `test_get_scan_status_pending`
- `test_get_scan_status_not_found`

**New file: `tests/test_logging.py`**
- `test_request_id_appears_in_response_headers`
- `test_request_id_in_log_output`

### Step 5.3: Update CI

**`.github/workflows/ci.yml`** — add monitoring deps:
```yaml
- run: pip install -e ".[test,monitoring]"
```

### Step 5.4: Update docs

- `AGENTS.md` — update API Endpoints table with `/api/v1/` prefix, add new endpoints
- `README.md` — update all curl examples and endpoint table
- `.env.example` — add `CORS_ORIGINS`, `ENABLE_METRICS`
- `CHANGELOG.md` — add v0.2.0 entry

---

## Execution Order

| # | Step | Files touched | Depends on |
|---|------|---------------|------------|
| 1 | CORS middleware | `config.py`, `main.py`, `.env.example`, `test_api.py` | — |
| 2 | API versioning | `api.py`, `test_api.py`, `test_dashboard_api.py`, `README.md`, `AGENTS.md` | — |
| 3 | Background scan jobs | `scanner/jobs.py` (new), `api.py`, `test_api.py` | — |
| 4 | Request ID middleware | `logging_config.py` (new), `main.py`, `cli.py` | — |
| 5 | Health check enhancement | `main.py` | — |
| 6 | Prometheus metrics | `config.py`, `main.py`, `pyproject.toml` | — |
| 7 | systemd service | `deploy/ns-lite.service` (new), `deploy/install.sh` (new) | — |
| 8 | Production Docker Compose | `docker-compose.prod.yml` (new), `.env.production` (new) | — |
| 9 | Test updates | `tests/test_api.py`, `tests/test_dashboard_api.py`, `tests/test_logging.py` (new) | 1-6 |
| 10 | Docs & changelog | `README.md`, `AGENTS.md`, `CHANGELOG.md`, `.env.example` | 1-8 |

Steps 1-3 can be done in parallel. Steps 4-6 can be done in parallel. Steps 7-8 can be done in parallel. Steps 9-10 are final cleanup.

---

## Verification

After each phase, run:
```bash
ruff check . && ruff format --check .
pytest -v
```

After Phase 5:
```bash
# Verify Docker build works
docker compose -f docker-compose.prod.yml build

# Verify systemd service file is valid
systemd-analyze verify deploy/ns-lite.service
```
