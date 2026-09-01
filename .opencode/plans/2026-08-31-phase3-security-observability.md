# Phase 3: Security & Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden ns-lite for production with security guards, startup validation, and health checks.

**Architecture:** Small targeted changes to auth.py, main.py, and config.py. No new dependencies.

**Tech Stack:** FastAPI, Python logging, SQLAlchemy

**Spec:** Design approved in brainstorming session — 5 security/observability changes.

## Global Constraints

- Python 3.10+ (pyproject.toml `requires-python = ">=3.10"`)
- ruff: line-length=120, target Python 3.10
- Existing tests must pass: `pytest -v`
- No new dependencies

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `netscan_lite/auth.py` | Modify | Guard dev auth behind DEBUG=true |
| `netscan_lite/main.py` | Modify | Health check with DB query, disable docs in prod |
| `netscan_lite/config.py` | Modify | Add startup validation method |
| `AGENTS.md` | Modify | Add TLS guidance |

---

### Task 1: Guard dev auth behind DEBUG=true

**Files:**
- Modify: `netscan_lite/auth.py:100-110`

**Interfaces:**
- Consumes: `settings.DEV_AUTH_ENABLED`, `settings.DEBUG`
- Produces: `get_current_user()` raises 401 unless DEBUG=true when dev auth is enabled

- [ ] **Step 1: Update get_current_user to check DEBUG**

In `netscan_lite/auth.py`, replace lines 100-110:

```python
async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPayload:
    """FastAPI dependency: validates JWT and returns the current user."""
    if not settings.LDAP_ENABLED:
        if not settings.DEV_AUTH_ENABLED:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Dev auth disabled. Set DEV_AUTH_ENABLED=true or LDAP_ENABLED=true.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not settings.DEBUG:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Dev auth requires DEBUG=true. Set DEBUG=true for development.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        logger.warning("Dev auth enabled — accepting any token as valid. Do not use in production.")
        return UserPayload(username=token, dn=f"cn={token},dev", groups=["dev-admin"])
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('netscan_lite/auth.py').read()); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add netscan_lite/auth.py
git commit -m "security: require DEBUG=true for dev auth bypass"
```

---

### Task 2: Add startup config validation

**Files:**
- Modify: `netscan_lite/config.py:35-72`

**Interfaces:**
- Consumes: `Settings` class fields
- Produces: `validate_production_config()` function that raises on invalid config

- [ ] **Step 1: Add validation method to Settings**

In `netscan_lite/config.py`, add after `model_post_init`:

```python
    def validate_production_config(self) -> list[str]:
        """Validate config for production use. Returns list of warnings."""
        warnings = []
        if self.LDAP_ENABLED and not self.LDAP_BIND_PASSWORD:
            warnings.append("LDAP_ENABLED=true but LDAP_BIND_PASSWORD is empty")
        if not self.LDAP_ENABLED and not self.DEV_AUTH_ENABLED and not self.DEBUG:
            warnings.append("Neither LDAP nor DEV_AUTH enabled — no authentication active")
        return warnings
```

- [ ] **Step 2: Call validation in lifespan**

In `netscan_lite/main.py`, update the lifespan function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Initializing ns-lite database...")
    init_db()
    if not settings.LDAP_ENABLED and settings.DEV_AUTH_ENABLED:
        if settings.DEBUG:
            logger.warning("DEV_AUTH_ENABLED is true — any token is accepted. Do not use in production.")
        else:
            logger.error("DEV_AUTH_ENABLED=true but DEBUG=false — dev auth will be rejected.")
    warnings = settings.validate_production_config()
    for w in warnings:
        logger.warning("Config warning: %s", w)
    logger.info("ns-lite ready")
    yield
    logger.info("ns-lite shutting down")
```

- [ ] **Step 3: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('netscan_lite/config.py').read()); print('config.py OK')" && python3 -c "import ast; ast.parse(open('netscan_lite/main.py').read()); print('main.py OK')"`

- [ ] **Step 4: Commit**

```bash
git add netscan_lite/config.py netscan_lite/main.py
git commit -m "feat: add startup config validation for production"
```

---

### Task 3: Health check verifies DB connectivity

**Files:**
- Modify: `netscan_lite/main.py:61-63`

**Interfaces:**
- Consumes: `engine` from `netscan_lite.db`
- Produces: `/health` returns `{"status": "healthy"}` only if DB query succeeds

- [ ] **Step 1: Update health check**

In `netscan_lite/main.py`, replace the health_check function:

```python
    @app.get("/health", tags=["System"])
    def health_check():
        from sqlalchemy import text
        from netscan_lite.db import engine

        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "healthy", "service": "ns-lite"}
        except Exception as e:
            logger.error("Health check failed: %s", e)
            return Response(
                content='{"status":"unhealthy","service":"ns-lite"}',
                status_code=503,
                media_type="application/json",
            )
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('netscan_lite/main.py').read()); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add netscan_lite/main.py
git commit -m "feat: health check now verifies database connectivity"
```

---

### Task 4: Disable /docs and /redoc in production

**Files:**
- Modify: `netscan_lite/main.py:49-54`

**Interfaces:**
- Consumes: `settings.DEBUG`
- Produces: FastAPI docs_url and redoc_url only set when DEBUG=true

- [ ] **Step 1: Conditionally set docs_url**

In `netscan_lite/main.py`, update the FastAPI constructor:

```python
    app = FastAPI(
        title="ns-lite API",
        description="Lightweight IP discovery with quarantine logic",
        version=app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('netscan_lite/main.py').read()); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add netscan_lite/main.py
git commit -m "security: disable Swagger/ReDoc in production (DEBUG=false)"
```

---

### Task 5: Add TLS guidance to AGENTS.md

**Files:**
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: existing AGENTS.md
- Produces: TLS documentation section

- [ ] **Step 1: Add TLS section to AGENTS.md**

After the "Production Deployment" section, add:

```markdown
### TLS / HTTPS

ns-lite runs plain HTTP. For production, place a reverse proxy in front:

**nginx:**
```nginx
server {
    listen 443 ssl;
    server_name ns-lite.internal;

    ssl_certificate /etc/ssl/certs/ns-lite.pem;
    ssl_certificate_key /etc/ssl/private/ns-lite.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**Caddy (simpler):**
```
ns-lite.internal {
    reverse_proxy localhost:8000
}
```

Caddy auto-provisions TLS via Let's Encrypt.
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: add TLS/reverse proxy guidance"
```

---

### Task 6: Final verification

- [ ] **Step 1: Verify all files parse correctly**

Run:
```bash
python3 -c "import ast; ast.parse(open('netscan_lite/auth.py').read()); print('auth.py OK')"
python3 -c "import ast; ast.parse(open('netscan_lite/main.py').read()); print('main.py OK')"
python3 -c "import ast; ast.parse(open('netscan_lite/config.py').read()); print('config.py OK')"
```

- [ ] **Step 2: Check git log**

Run: `git log --oneline -6`
Expected: 6 new commits (Tasks 1-5 + any intermediate)

- [ ] **Step 3: Verify AGENTS.md has all sections**

Run: `grep "^##" AGENTS.md`
Expected: All sections present including "Database Migrations" and "TLS / HTTPS"
