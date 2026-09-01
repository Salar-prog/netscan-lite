# Production Readiness Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all critical, high, and medium production readiness issues from the audit.

**Architecture:** Security hardening (LDAP injection, rate limiting, upload limits, input validation), performance fixes (N+1 queries, pagination), and Docker/security hardening. Each task is a self-contained commit.

**Tech Stack:** Python 3.10+, FastAPI, SQLModel, ldap3, Docker, React

**Spec:** `docs/PRODUCTION_READINESS_AUDIT.md`

## Global Constraints

- Python 3.10+ (`requires-python = ">=3.10"`)
- ruff: line-length=120, target Python 3.10
- No new dependencies unless absolutely necessary (discuss first)
- Follow existing code patterns in the codebase
- Each task produces a working, testable change

---

## File Map

| File | Changes |
|------|---------|
| `netscan_lite/auth.py` | LDAP injection fix |
| `netscan_lite/api.py` | Rate limiting, upload limit, WS validation, auth consistency, N+1 fixes, error sanitization, updated_at, uuid import |
| `netscan_lite/cli.py` | Token file perms, redundant import |
| `netscan_lite/main.py` | Security headers, CSP fix |
| `netscan_lite/scanner/runner.py` | Error message sanitization |
| `netscan_lite/dashboard/src/components/Import.tsx` | IP regex fix |
| `Dockerfile` | Non-root user |
| `docker-compose.yml` | Remove DB port exposure |
| `alembic.ini` | Remove hardcoded URL |
| `tests/test_auth.py` | New: LDAP injection tests |
| `tests/test_api.py` | New: upload limit, rate limit tests |
| `tests/test_websocket.py` | New: WS validation tests |

---

### Task 1: Fix LDAP Injection (CRITICAL #1)

**Files:**
- Modify: `netscan_lite/auth.py:40`
- Create: `tests/test_auth.py`

**Interfaces:**
- Consumes: `username` string from login form
- Produces: sanitized username in LDAP filter

- [ ] **Step 1: Add LDAP escape helper to auth.py**

```python
def _escape_ldap_value(value: str) -> str:
    """Escape special characters for LDAP filter values (RFC 4515)."""
    escaped = value.replace("\\", "\\5c")
    escaped = escaped.replace("*", "\\2a")
    escaped = escaped.replace("(", "\\28")
    escaped = escaped.replace(")", "\\29")
    escaped = escaped.replace("\x00", "\\00")
    return escaped
```

- [ ] **Step 2: Apply escape in _ldap_authenticate_sync**

Change line 40 from:
```python
search_filter = settings.LDAP_SEARCH_FILTER.format(username=username)
```
To:
```python
safe_username = _escape_ldap_value(username)
search_filter = settings.LDAP_SEARCH_FILTER.format(username=safe_username)
```

- [ ] **Step 3: Write test for LDAP injection prevention**

Create `tests/test_auth.py`:
```python
"""Tests for auth module security."""

from netscan_lite.auth import _escape_ldap_value


def test_escape_ldap_value_special_chars():
    assert _escape_ldap_value("admin*)") == "admin\\2a\\29"


def test_escape_ldap_value_parentheses():
    assert _escape_ldap_value("(cn=admin)") == "\\28cn=admin\\29"


def test_escape_ldap_value_asterisk():
    assert _escape_ldap_value("*") == "\\2a"


def test_escape_ldap_value_backslash():
    assert _escape_ldap_value("test\\value") == "test\\5cvalue"


def test_escape_ldap_value_null():
    assert _escape_ldap_value("test\x00value") == "test\\00value"


def test_escape_ldap_value_normal():
    assert _escape_ldap_value("jsmith") == "jsmith"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_auth.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add netscan_lite/auth.py tests/test_auth.py
git commit -m "fix: escape LDAP special chars in username to prevent injection (CRITICAL #1)"
```

---

### Task 2: Require group or ips for /scan (CRITICAL #3)

**Files:**
- Modify: `netscan_lite/api.py:175-197`

**Interfaces:**
- Consumes: `ScanRequest` from client
- Produces: HTTP 400 if neither group nor ips provided

- [ ] **Step 1: Modify trigger_scan to require group or ips**

Replace the else branch (lines 191-194):
```python
    else:
        ips = session.exec(select(IPAddress)).all()
        target_ips = [i.ip for i in ips]
        group_obj = None
```

With:
```python
    else:
        raise HTTPException(
            status_code=400,
            detail="Either 'group' or 'ips' must be provided. Omitting both would scan all IPs."
        )
```

- [ ] **Step 2: Update tests**

In `tests/test_api.py`, update `test_scan_no_ips` and add:
```python
def test_scan_no_group_or_ips(client, auth_headers):
    resp = client.post("/api/scan", json={}, headers=auth_headers)
    assert resp.status_code == 400
    assert "group" in resp.json()["detail"]
```

- [ ] **Step 3: Commit**

```bash
git add netscan_lite/api.py tests/test_api.py
git commit -m "fix: require group or ips in POST /scan to prevent accidental full DB sweep (CRITICAL #3)"
```

---

### Task 3: Add Upload Size Limit (CRITICAL #4)

**Files:**
- Modify: `netscan_lite/api.py:515-552`

**Interfaces:**
- Consumes: uploaded file
- Produces: HTTP 413 if file exceeds 10MB

- [ ] **Step 1: Add size check before reading file**

Replace:
```python
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)
```

With:
```python
    # Check file size (10MB limit)
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)}MB."
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
```

- [ ] **Step 2: Add test for upload size limit**

In `tests/test_dashboard_api.py`, add:
```python
def test_import_file_too_large(db_engine, client, auth_headers):
    # Create a 11MB fake CSV content
    large_content = b"ip,hostname\n" + b"10.0.0.1,host1\n" * 500000
    resp = client.post(
        "/api/import",
        files={"file": ("large.csv", io.BytesIO(large_content), "text/csv")},
        headers=auth_headers,
    )
    assert resp.status_code == 413
```

- [ ] **Step 3: Commit**

```bash
git add netscan_lite/api.py tests/test_dashboard_api.py
git commit -m "fix: add 10MB upload size limit to prevent OOM attacks (CRITICAL #4)"
```

---

### Task 4: Add Rate Limiting (CRITICAL #6)

**Files:**
- Modify: `netscan_lite/api.py`
- Modify: `netscan_lite/main.py`

**Interfaces:**
- Consumes: incoming requests
- Produces: HTTP 429 when rate exceeded

- [ ] **Step 1: Add simple in-memory rate limiter to api.py**

Add at the top of api.py (after imports):
```python
import time
from collections import defaultdict
from typing import Dict, List

# Simple in-memory rate limiter
_rate_limit_store: Dict[str, List[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 30  # per window per IP


def _check_rate_limit(ip: str) -> bool:
    """Check if request is within rate limit. Returns True if allowed."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    # Remove old entries
    _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if t > cutoff]
    if len(_rate_limit_store[ip]) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    _rate_limit_store[ip].append(now)
    return True
```

- [ ] **Step 2: Apply rate limit to /token endpoint**

In the `login` function, add at the top:
```python
    # Rate limit: 5 attempts per minute per IP
    from fastapi import Request as Req
    # Note: We can't easily get the client IP in this context,
    # so we'll apply a simpler global rate limit
```

Actually, for simplicity, apply rate limiting via middleware in main.py instead.

- [ ] **Step 3: Add rate limit middleware to main.py**

Add after SecurityHeadersMiddleware:
```python
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 60, window: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window
        self._store: Dict[str, List[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - self.window
        self._store[client_ip] = [t for t in self._store[client_ip] if t > cutoff]
        if len(self._store[client_ip]) >= self.max_requests:
            return Response(
                content='{"detail":"Rate limit exceeded. Try again later."}',
                status_code=429,
                media_type="application/json",
            )
        self._store[client_ip].append(now)
        return await call_next(request)
```

Add to create_app:
```python
    app.add_middleware(RateLimitMiddleware, max_requests=120, window=60)
```

- [ ] **Step 4: Commit**

```bash
git add netscan_lite/main.py
git commit -m "fix: add rate limiting middleware (60 req/min per IP) (CRITICAL #6)"
```

---

### Task 5: Token File Permissions (HIGH #7)

**Files:**
- Modify: `netscan_lite/cli.py:266`

**Interfaces:**
- Consumes: JWT token string
- Produces: token file with 0o600 permissions

- [ ] **Step 1: Add chmod after write**

Change:
```python
    token_file.write_text(result["access_token"])
```
To:
```python
    token_file.write_text(result["access_token"])
    token_file.chmod(0o600)
```

- [ ] **Step 2: Commit**

```bash
git add netscan_lite/cli.py
git commit -m "fix: set restrictive permissions (0o600) on token file (HIGH #7)"
```

---

### Task 6: Sanitize nmap Error Messages (HIGH #8)

**Files:**
- Modify: `netscan_lite/scanner/runner.py:126-128`
- Modify: `netscan_lite/api.py:204,340`

**Interfaces:**
- Consumes: RuntimeError from nmap
- Produces: generic error message to API clients

- [ ] **Step 1: Sanitize error in runner.py**

Change:
```python
        if process.returncode != 0 and not stdout:
            err_msg = stderr.decode(errors="replace")
            raise RuntimeError(f"Nmap exited with code {process.returncode}: {err_msg}")
```
To:
```python
        if process.returncode != 0 and not stdout:
            logger.error("Nmap failed with code %d: %s", process.returncode, stderr.decode(errors="replace"))
            raise RuntimeError("Nmap scan failed")
```

- [ ] **Step 2: Commit**

```bash
git add netscan_lite/scanner/runner.py
git commit -m "fix: sanitize nmap error messages to prevent information leakage (HIGH #8)"
```

---

### Task 7: Sanitize Import Error Messages (HIGH #9)

**Files:**
- Modify: `netscan_lite/api.py:544-550`

**Interfaces:**
- Consumes: exception from importer
- Produces: generic error message

- [ ] **Step 1: Change except block**

Change:
```python
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```
To:
```python
    except Exception as e:
        logger.error("Import failed: %s", e)
        raise HTTPException(status_code=400, detail="Import failed. Check file format and content.")
```

- [ ] **Step 2: Commit**

```bash
git add netscan_lite/api.py
git commit -m "fix: sanitize import error messages to prevent path leakage (HIGH #9)"
```

---

### Task 8: WebSocket Input Validation (HIGH #10)

**Files:**
- Modify: `netscan_lite/api.py:579-596`

**Interfaces:**
- Consumes: JSON from WebSocket client
- Produces: validated IP list

- [ ] **Step 1: Add IP validation to WS handler**

After `ips = data.get("ips")`, add validation:
```python
    # Validate IPs if provided
    if ips:
        validated_ips = []
        for ip_str in ips:
            try:
                ipaddress.IPv4Address(ip_str.strip())
                validated_ips.append(ip_str.strip())
            except ValueError:
                await websocket.send_json({"type": "error", "detail": f"Invalid IP address: {ip_str}"})
                await websocket.close()
                return
        ips = validated_ips
```

- [ ] **Step 2: Commit**

```bash
git add netscan_lite/api.py
git commit -m "fix: validate IP addresses in WebSocket scan endpoint (HIGH #10)"
```

---

### Task 9: WebSocket Auth Consistency (HIGH #11)

**Files:**
- Modify: `netscan_lite/api.py:567-570`

**Interfaces:**
- Consumes: auth settings
- Produces: consistent auth behavior

- [ ] **Step 1: Add DEBUG check to WS handler**

Change:
```python
    elif not settings.DEV_AUTH_ENABLED:
        await websocket.close(code=4001, reason="Dev auth disabled")
        return
    # Dev mode: any token accepted
```
To:
```python
    elif not settings.DEV_AUTH_ENABLED:
        await websocket.close(code=4001, reason="Dev auth disabled")
        return
    elif not settings.DEBUG:
        await websocket.close(code=4001, reason="Dev auth requires DEBUG=true")
        return
    # Dev mode: any token accepted
```

- [ ] **Step 2: Commit**

```bash
git add netscan_lite/api.py
git commit -m "fix: align WebSocket auth with REST API — require DEBUG=true for dev auth (HIGH #11)"
```

---

### Task 10: Move uuid Imports (HIGH #12)

**Files:**
- Modify: `netscan_lite/api.py:427,468`
- Modify: `netscan_lite/api.py` (top-level import)

**Interfaces:**
- Consumes: uuid module
- Produces: top-level import

- [ ] **Step 1: Move import to top of file**

Add `import uuid` at the top of api.py (after line 1).

- [ ] **Step 2: Remove local imports**

Remove `import uuid` from inside `update_group()` (line 427) and `delete_group()` (line 468).

- [ ] **Step 3: Commit**

```bash
git add netscan_lite/api.py
git commit -m "fix: move uuid import to top level to avoid repeated imports (HIGH #12)"
```

---

### Task 11: Docker Non-Root User (HIGH #13)

**Files:**
- Modify: `Dockerfile:24-37`

**Interfaces:**
- Consumes: runtime image
- Produces: non-root user for web server

- [ ] **Step 1: Add non-root user to Dockerfile**

Before the EXPOSE line, add:
```dockerfile
# Create non-root user (nmap needs root for raw sockets, but web server doesn't)
RUN useradd -m -s /bin/bash ns-lite

# Give nmap suid capability for unprivileged scans
RUN chmod u+s /usr/bin/nmap

USER ns-lite
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile
git commit -m "fix: run container as non-root user with nmap suid (HIGH #13)"
```

---

### Task 12: Remove DB Port Exposure (HIGH #14)

**Files:**
- Modify: `docker-compose.yml:11`

**Interfaces:**
- Consumes: docker-compose config
- Produces: DB only accessible via Docker network

- [ ] **Step 1: Remove port mapping**

Change:
```yaml
    ports:
      - "5432:5432"
```
To:
```yaml
    # DB only accessible via Docker network (not exposed to host)
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "fix: remove PostgreSQL port exposure from host (HIGH #14)"
```

---

### Task 13: Fix N+1 in groups-detail (MEDIUM #15)

**Files:**
- Modify: `netscan_lite/api.py:396-416`

**Interfaces:**
- Consumes: Group and IPAddress tables
- Produces: single query with counts

- [ ] **Step 1: Rewrite list_groups_detail**

Replace the function body with:
```python
    groups = session.exec(select(Group)).all()
    if not groups:
        return []

    # Single query for all group IP counts
    count_query = select(IPAddress.group_id, func.count(IPAddress.id)).group_by(IPAddress.group_id)
    counts = dict(session.exec(count_query).all())

    return [
        GroupDetailResponse(
            id=str(g.id),
            name=g.name,
            description=g.description,
            miss_threshold=g.miss_threshold,
            quarantine_hours=g.quarantine_hours,
            ip_count=counts.get(g.id, 0),
        )
        for g in groups
    ]
```

- [ ] **Step 2: Commit**

```bash
git add netscan_lite/api.py
git commit -m "fix: optimize groups-detail to single query instead of N+1 (MEDIUM #15)"
```

---

### Task 14: Fix N+1 in stats (MEDIUM #16)

**Files:**
- Modify: `netscan_lite/api.py:356-388`

**Interfaces:**
- Consumes: IPAddress table
- Produces: single query for all stats

- [ ] **Step 1: Rewrite get_stats**

Replace the function body with:
```python
    # Single query for all status counts
    status_counts = dict(
        session.exec(
            select(IPAddress.status, func.count(IPAddress.id)).group_by(IPAddress.status)
        ).all()
    )

    total = sum(status_counts.values())
    group_count = session.exec(select(func.count(Group.id))).one()

    last_ip = session.exec(
        select(IPAddress).where(IPAddress.last_scanned_at.is_not(None)).order_by(IPAddress.last_scanned_at.desc())
    ).first()
    last_scan = str(last_ip.last_scanned_at) if last_ip and last_ip.last_scanned_at else None

    return StatsResponse(
        total_ips=total,
        active=status_counts.get(IPStatus.ACTIVE_DETECTED, 0),
        uncertain=status_counts.get(IPStatus.UNCERTAIN_FIREWALLED, 0),
        available=status_counts.get(IPStatus.AVAILABLE_CANDIDATE, 0),
        reserved=status_counts.get(IPStatus.ASSIGNED_RESERVED, 0),
        groups=group_count,
        last_scan=last_scan,
    )
```

- [ ] **Step 2: Commit**

```bash
git add netscan_lite/api.py
git commit -m "fix: optimize stats endpoint to single query instead of 6 separate counts (MEDIUM #16)"
```

---

### Task 15: Fix Pagination Count (MEDIUM #17)

**Files:**
- Modify: `netscan_lite/api.py:264`

**Interfaces:**
- Consumes: IPAddress query
- Produces: count without loading all rows

- [ ] **Step 1: Use func.count for total**

Change:
```python
    total = len(session.exec(query).all())
```
To:
```python
    count_query = select(func.count()).select_from(query.subquery())
    total = session.exec(count_query).one()
```

- [ ] **Step 2: Commit**

```bash
git add netscan_lite/api.py
git commit -m "fix: use COUNT subquery for pagination instead of loading all rows (MEDIUM #17)"
```

---

### Task 16: Update updated_at on Group Changes (MEDIUM #19)

**Files:**
- Modify: `netscan_lite/api.py:438-447`

**Interfaces:**
- Consumes: group update request
- Produces: updated timestamp

- [ ] **Step 1: Add updated_at update**

After the field assignments, add:
```python
    group.updated_at = utc_now()
```

- [ ] **Step 2: Add import for utc_now**

Add `from netscan_lite.models import utc_now` at the top of api.py.

- [ ] **Step 3: Commit**

```bash
git add netscan_lite/api.py
git commit -m "fix: update updated_at timestamp when group settings change (MEDIUM #19)"
```

---

### Task 17: Fix Cascade Delete Uncertainty (MEDIUM #20)

**Files:**
- Modify: `netscan_lite/api.py:479`

**Interfaces:**
- Consumes: group to delete
- Produces: reliable cascade delete

- [ ] **Step 1: Load ips relationship before delete**

Change:
```python
    session.delete(group)
    session.commit()
```
To:
```python
    # Ensure ips are loaded for cascade delete
    _ = group.ips
    session.delete(group)
    session.commit()
```

- [ ] **Step 2: Commit**

```bash
git add netscan_lite/api.py
git commit -m "fix: ensure ips relationship loaded before cascade delete (MEDIUM #20)"
```

---

### Task 18: Fix alembic.ini Misleading URL (MEDIUM #22)

**Files:**
- Modify: `alembic.ini:4`

**Interfaces:**
- Consumes: alembic config
- Produces: clear config that env.py handles URL

- [ ] **Step 1: Remove hardcoded URL**

Change:
```ini
sqlalchemy.url = sqlite:///./ns-lite.db
```
To:
```ini
# Database URL is configured via DATABASE_URL env var (see config.py)
# sqlalchemy.url is overridden in alembic/env.py
```

- [ ] **Step 2: Commit**

```bash
git add alembic.ini
git commit -m "fix: remove misleading hardcoded SQLite URL from alembic.ini (MEDIUM #22)"
```

---

### Task 19: Fix Frontend IP Regex (MEDIUM #26)

**Files:**
- Modify: `netscan_lite/dashboard/src/components/Import.tsx:31`

**Interfaces:**
- Consumes: IP string from CSV
- Produces: validated IP

- [ ] **Step 1: Improve IP regex**

Change:
```typescript
const valid = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(ip)
```
To:
```typescript
const valid = /^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$/.test(ip)
```

- [ ] **Step 2: Commit**

```bash
git add netscan_lite/dashboard/src/components/Import.tsx
git commit -m "fix: validate IP octets are 0-255 in frontend regex (MEDIUM #26)"
```

---

### Task 20: Add Security Headers (MEDIUM #25)

**Files:**
- Modify: `netscan_lite/main.py:16-25`

**Interfaces:**
- Consumes: HTTP responses
- Produces: additional security headers

- [ ] **Step 1: Add missing headers to SecurityHeadersMiddleware**

Add after existing headers:
```python
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
```

- [ ] **Step 2: Commit**

```bash
git add netscan_lite/main.py
git commit -m "fix: add HSTS, Referrer-Policy, and Permissions-Policy headers (MEDIUM #25)"
```

---

### Task 21: Fix Redundant Import (MEDIUM #29)

**Files:**
- Modify: `netscan_lite/cli.py:242`

**Interfaces:**
- Consumes: json module
- Produces: consistent import

- [ ] **Step 1: Remove redundant local import**

Remove `import json as json_mod` from inside the `auth` function.

Change:
```python
    result = json_mod.loads(resp.read().decode())
```
To:
```python
    result = json.loads(resp.read().decode())
```

- [ ] **Step 2: Commit**

```bash
git add netscan_lite/cli.py
git commit -m "fix: remove redundant local json import in auth command (MEDIUM #29)"
```

---

### Task 22: Final Verification

- [ ] **Step 1: Run ruff check**

```bash
ruff check .
```

- [ ] **Step 2: Run ruff format check**

```bash
ruff format --check .
```

- [ ] **Step 3: Run tests**

```bash
pytest -v
```

- [ ] **Step 4: Check git status**

```bash
git status
git log --oneline -15
```

- [ ] **Step 5: Push to origin**

```bash
git push origin main
```
