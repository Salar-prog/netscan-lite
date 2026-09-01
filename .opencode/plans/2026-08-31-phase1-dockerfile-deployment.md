# Phase 1: Dockerfile & Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ns-lite deployable via Docker and bare metal with production-grade settings.

**Architecture:** Fix the Dockerfile to build the dashboard, add multi-worker support via gunicorn, provide docker-compose for PostgreSQL, and add a `.dockerignore`.

**Tech Stack:** Docker multi-stage build, Node.js 20 (dashboard), gunicorn + uvicorn workers, PostgreSQL (docker-compose), Python 3.12

**Spec:** No separate spec — design was approved in brainstorming session (Phase 1: Dockerfile & Deployment).

## Global Constraints

- Python 3.10+ (pyproject.toml `requires-python = ">=3.10"`)
- ruff: line-length=120, target Python 3.10
- No new dependencies without discussion (gunicorn is approved as part of this plan)
- Existing tests must pass: `pytest -v`
- Existing lint must pass: `ruff check . && ruff format --check .`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `Dockerfile` | Rewrite | Multi-stage: Node.js build dashboard, Python runtime with gunicorn |
| `.dockerignore` | Create | Exclude .git, node_modules, tests, docs, .env, *.db |
| `docker-compose.yml` | Create | PostgreSQL + app with env vars |
| `pyproject.toml` | Modify | Add `gunicorn` dependency |
| `netscan_lite/cli.py` | Modify | Add `--workers` and `--log-level` options to `serve` |
| `.env.example` | Modify | Add PostgreSQL and production vars |
| `AGENTS.md` | Modify | Update Docker/deployment docs |

---

### Task 1: Add gunicorn dependency

**Files:**
- Modify: `pyproject.toml:15-24`

**Interfaces:**
- Consumes: existing `[project.dependencies]` list
- Produces: gunicorn available for `pip install -e ".[test]"` or in Docker image

- [ ] **Step 1: Add gunicorn to dependencies**

Edit `pyproject.toml`, add `"gunicorn>=21.2"` to the `dependencies` list after `"python-multipart>=0.0.6"`.

- [ ] **Step 2: Verify existing tests still pass**

Run: `pytest -v`
Expected: All 84 tests pass (gunicorn is not imported by tests)

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add gunicorn for production serving"
```

---

### Task 2: Add --workers flag to CLI serve command

**Files:**
- Modify: `netscan_lite/cli.py:183-193`

**Interfaces:**
- Consumes: existing `create_app()` from `netscan_lite.main`
- Produces: `ns-lite serve --workers 4` launches gunicorn; `ns-lite serve` (no flag) stays single-worker uvicorn for dev

- [ ] **Step 1: Update the serve command**

Replace the `serve` function in `cli.py` (lines 183-193) with:

```python
@cli.command()
@click.option("--host", default="0.0.0.0", help="Bind host")
@click.option("--port", default=8000, type=int, help="Bind port")
@click.option("--workers", default=1, type=int, help="Number of uvicorn workers (1 = single-process dev mode)")
@click.option("--log-level", default="info", type=click.Choice(["debug", "info", "warning", "error"]), help="Log level")
def serve(host: str, port: int, workers: int, log_level: str):
    """Start the API server."""
    from netscan_lite.main import create_app

    app = create_app()

    if workers > 1:
        import gunicorn.app.base

        class StandaloneApplication(gunicorn.app.base.BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    if key in self.cfg.settings and value is not None:
                        self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        options = {
            "bind": f"{host}:{port}",
            "workers": workers,
            "worker_class": "uvicorn.workers.UvicornWorker",
            "loglevel": log_level,
        }
        StandaloneApplication(app, options).run()
    else:
        import uvicorn

        uvicorn.run(app, host=host, port=port, log_level=log_level)
```

- [ ] **Step 2: Verify lint passes**

Run: `ruff check netscan_lite/cli.py && ruff format --check netscan_lite/cli.py`
Expected: PASS

- [ ] **Step 3: Verify tests pass**

Run: `pytest -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add netscan_lite/cli.py
git commit -m "feat: add --workers flag to serve command for production gunicorn"
```

---

### Task 3: Create .dockerignore

**Files:**
- Create: `.dockerignore`

**Interfaces:**
- Consumes: none
- Produces: Docker build context excludes unnecessary files

- [ ] **Step 1: Create .dockerignore**

```
.git
.github
.env
.env.*
!.env.example
*.db
*.sqlite3
.pytest_cache
.coverage
htmlcov
.ruff_cache
site/
docs/
tests/
netscan_lite/dashboard/node_modules/
netscan_lite/dashboard/.vite/
*.md
!README.md
```

- [ ] **Step 2: Commit**

```bash
git add .dockerignore
git commit -m "chore: add .dockerignore for faster builds"
```

---

### Task 4: Rewrite Dockerfile with dashboard build stage

**Files:**
- Rewrite: `Dockerfile`

**Interfaces:**
- Consumes: `.dockerignore`, `pyproject.toml`, `netscan_lite/dashboard/package.json`
- Produces: Working Docker image with dashboard, gunicorn, nmap

- [ ] **Step 1: Rewrite Dockerfile**

```dockerfile
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
```

- [ ] **Step 2: Verify Docker builds locally**

Run: `docker build -t ns-lite:test .`
Expected: Build succeeds, image is created

- [ ] **Step 3: Verify container starts and health check passes**

Run: `docker run -d --name ns-lite-test -p 8000:8000 ns-lite:test && sleep 5 && curl http://localhost:8000/health`
Expected: `{"status":"healthy","service":"ns-lite"}`

- [ ] **Step 4: Verify dashboard is served**

Run: `curl -s http://localhost:8000/ | head -5`
Expected: HTML content (React SPA index.html)

- [ ] **Step 5: Cleanup and commit**

Run: `docker rm -f ns-lite-test`
```bash
git add Dockerfile
git commit -m "fix: rebuild Dockerfile with Node.js stage for dashboard + gunicorn"
```

---

### Task 5: Create docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

**Interfaces:**
- Consumes: Dockerfile, `.env.example`
- Produces: One-command deployment with PostgreSQL

- [ ] **Step 1: Create docker-compose.yml**

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: netscan
      POSTGRES_USER: netscan
      POSTGRES_PASSWORD: ${DB_PASSWORD:-netscan_dev}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U netscan"]
      interval: 5s
      timeout: 5s
      retries: 5

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://netscan:${DB_PASSWORD:-netscan_dev}@db:5432/netscan
      LDAP_ENABLED: ${LDAP_ENABLED:-false}
      DEV_AUTH_ENABLED: ${DEV_AUTH_ENABLED:-false}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY:-}
      WORKERS: ${WORKERS:-2}
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pgdata:
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add docker-compose with PostgreSQL"
```

---

### Task 6: Update .env.example with production vars

**Files:**
- Modify: `.env.example`

**Interfaces:**
- Consumes: existing `.env.example`
- Produces: Documented production configuration

- [ ] **Step 1: Update .env.example**

Add PostgreSQL and production-specific vars at the end of `.env.example`:

```bash
# PostgreSQL (used with docker-compose)
DB_PASSWORD=change_me_in_production

# Production server
WORKERS=2

# API base URL (used by CLI auth command)
API_BASE_URL=http://127.0.0.1:8000
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add PostgreSQL and production vars to .env.example"
```

---

### Task 7: Update AGENTS.md with deployment docs

**Files:**
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: all previous tasks
- Produces: Documented deployment workflow

- [ ] **Step 1: Add deployment section to AGENTS.md**

After the "Dashboard Development" section, add a new "Production Deployment" section:

```markdown
## Production Deployment

### Docker (recommended)

```bash
# Build and start with PostgreSQL
docker compose up -d

# Check logs
docker compose logs -f app

# Stop
docker compose down
```

### Bare Metal

```bash
pip install -e ".[xlsx]"

# Start with multiple workers
ns-lite serve --host 0.0.0.0 --port 8000 --workers 4

# Or single worker for dev
ns-lite serve
```

### Environment Variables for Production

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `LDAP_ENABLED` | Yes | Set to `true` for production auth |
| `LDAP_SERVER` | If LDAP enabled | LDAP server URL |
| `LDAP_BIND_DN` | If LDAP enabled | Service account DN |
| `LDAP_BIND_PASSWORD` | If LDAP enabled | Service account password |
| `JWT_SECRET_KEY` | Recommended | Token signing key (auto-generated if not set) |
| `WORKERS` | No | Gunicorn workers (default: 1) |
| `DB_PASSWORD` | If using docker-compose | PostgreSQL password |
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: add production deployment guide to AGENTS.md"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: All 84 tests pass

- [ ] **Step 2: Run lint and format checks**

Run: `ruff check . && ruff format --check .`
Expected: PASS

- [ ] **Step 3: Verify Docker build still works**

Run: `docker build -t ns-lite:final .`
Expected: Build succeeds

- [ ] **Step 4: Verify compose config is valid**

Run: `docker compose config`
Expected: Valid YAML, no errors
