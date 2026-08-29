# Launch Prep Plan — Security & Operational Fixes

**Date:** 2026-08-29
**Scope:** 7 items to make ns-lite production-ready
**Status:** In Progress

---

## Item 1: Persist JWT Secret Across Restarts

### Problem
`config.py:34` — `JWT_SECRET_KEY: str = secrets.token_urlsafe(32)` runs at import time.
Every server restart generates a new secret, invalidating all existing tokens.

### Solution
File-based secret persistence at `~/.ns-lite/jwt-secret`.

**Logic (in `config.py`):**
1. If `JWT_SECRET_KEY` env var is explicitly set → use it (manual override)
2. Else, check `~/.ns-lite/jwt-secret` → read and use it
3. Else, generate `secrets.token_urlsafe(32)`, write to `~/.ns-lite/jwt-secret`, use it

**Implementation:**
- Add `_resolve_jwt_secret()` function in `config.py`
- Call it in `Settings.model_post_init()` to set the default
- Create `~/.ns-lite/` directory if it doesn't exist (use `Path.home() / ".ns-lite"`)
- File permissions: `0o600` (owner read/write only)

**Files:**
- `netscan_lite/config.py` — add `_resolve_jwt_secret()`, update `JWT_SECRET_KEY` default

**Tests:**
- New test: verify secret file is created on first call
- New test: verify existing secret file is reused
- Existing tests: unaffected (dev mode doesn't validate JWT)

---

## Item 2: Guard Dev-Mode Auth

### Problem
`auth.py:102-104` — when `LDAP_ENABLED=false`, any string is accepted as a valid user.
No explicit opt-in, no startup warning. Dangerous if deployed without `LDAP_ENABLED=true`.

### Solution
Add `DEV_AUTH_ENABLED: bool = False` config flag.

**Logic (in `auth.py:get_current_user`):**
```
if not LDAP_ENABLED:
    if not DEV_AUTH_ENABLED:
        raise HTTPException(401, "Dev auth disabled. Set DEV_AUTH_ENABLED=true or LDAP_ENABLED=true.")
    log warning once
    return UserPayload(username=token, ...)
```

**Implementation:**
- Add `DEV_AUTH_ENABLED: bool = False` to `Settings` in `config.py`
- Update `auth.py:get_current_user` to check both flags
- Log a warning at startup in `main.py:lifespan` if dev auth is enabled
- Update `.env.example` with new flag and documentation

**Files:**
- `netscan_lite/config.py` — add `DEV_AUTH_ENABLED`
- `netscan_lite/auth.py` — update `get_current_user`
- `netscan_lite/main.py` — add startup warning
- `.env.example` — document new flag

**Tests:**
- Update `conftest.py`: set `DEV_AUTH_ENABLED=true` via monkeypatch so existing tests pass
- New test: verify 401 when both `LDAP_ENABLED=false` and `DEV_AUTH_ENABLED=false`
- New test: verify auth works when `DEV_AUTH_ENABLED=true`

---

## Item 3: Escape LIKE Patterns

### Problem
`api.py:256` — `IPAddress.ip.like(f"%{search}%")` passes user input directly into SQL LIKE.
`%` and `_` in search terms are not escaped, allowing pattern matching abuse.

### Solution
Add `_escape_like(value: str) -> str` helper that escapes `%` and `_` with backslashes.

**Implementation:**
- Add helper function in `api.py`
- Apply before constructing search pattern:
  ```python
  safe = _escape_like(search)
  search_pattern = f"%{safe}%"
  ```

**Files:**
- `netscan_lite/api.py` — add `_escape_like()`, update `list_ips` endpoint

**Tests:**
- New test: search for term containing `%` returns literal match
- New test: search for term containing `_` returns literal match

---

## Item 4: Add Security Headers

### Problem
No `Content-Security-Policy`, `X-Content-Type-Options`, or `X-Frame-Options` on responses.

### Solution
Add Starlette middleware in `main.py`.

**Headers:**
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:`

**Implementation:**
- Add `SecurityHeadersMiddleware` class in `main.py`
- Register in `create_app()` before static file mount

**Files:**
- `netscan_lite/main.py` — add middleware

**Tests:**
- New test: verify security headers present on `/health` response
- New test: verify headers present on API responses

---

## Item 5: Create Dockerfile

### Problem
`docs/install.md` references Docker build/run but no Dockerfile exists.

### Solution
Minimal multi-stage Dockerfile.

**Stage 1 (builder):**
- `python:3.12-slim`
- Install nmap
- Copy source, install with `pip install -e ".[xlsx]"`

**Stage 2 (runtime):**
- `python:3.12-slim`
- Install nmap (runtime only)
- Copy installed packages from builder
- Expose 8000
- `CMD ["ns-lite", "serve", "--host", "0.0.0.0"]`

**Files:**
- `Dockerfile` (new)

**Tests:** N/A (manual verification)

---

## Item 6: Remove Dead Code

### Problem
Three pieces of dead code:
- `custom_metadata` on `IPAddress` — written but never read
- `EventType` enum + `event_type`/`event_details` on `ClassificationOutcome` — set but never stored
- `raw_extra` on `HostProbeResult` — populated but never accessed

### Solution
Remove all three.

**Implementation:**
- `models.py`: Remove `EventType` enum (lines 21-23), remove `custom_metadata` field (line 62)
- `importer.py`: Remove `custom_metadata={"imported_from": ..., "row": i}` from IPAddress creation (line 124)
- `classifier.py`: Remove `event_type` and `event_details` from `ClassificationOutcome` dataclass, remove all assignments
- `classifier.py`: Remove `EventType` from import
- `runner.py`: Remove `raw_extra` field from `HostProbeResult` (line 53), remove assignment (line 218)

**Files:**
- `netscan_lite/models.py`
- `netscan_lite/importer.py`
- `netscan_lite/scanner/classifier.py`
- `netscan_lite/scanner/runner.py`

**Tests:** All existing tests should pass unchanged (none assert on these fields)

---

## Item 7: Fix AGENTS.md Stale Reference

### Problem
Line 72 says `cidr.py` "exists on disk but is dead code" — the file was removed.

### Solution
Remove the `cidr.py` note entirely.

**Files:**
- `AGENTS.md`

---

## Execution Order

1. Items 1-4 (security) — independent, can be implemented sequentially
2. Items 5-7 (operational) — independent, can be implemented after 1-4
3. Run full test suite
4. Lint + format
5. Commit and push

## Verification

After all changes:
- `pytest -v` — all 84+ tests pass
- `ruff check . && ruff format --check .` — clean
- `npm run build` — dashboard builds
- Manual: verify `~/.ns-lite/jwt-secret` is created on first run
- Manual: verify 401 when dev auth disabled
- Manual: verify security headers on responses
