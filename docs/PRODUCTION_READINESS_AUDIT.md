# Production Readiness Audit: ns-lite

> **Note:** This is a historical audit snapshot from v0.1.0. Several items have been addressed in v0.2.0 (CORS, API versioning, async scan jobs, readiness probes, structured logging). See [CHANGELOG.md](../CHANGELOG.md) for current status.

**Date:** 2026-08-31 (updated 2026-09-01)
**Auditor:** Senior Code Review
**Scope:** Full codebase analysis — security, bugs, over-engineering, production blockers

---

## STILL OPEN — Remaining Issues

### CRITICAL

#### 1. Synchronous `/api/v1/scan` Blocks Workers (api.py:176-211)
`trigger_scan` is `async def` but calls `await scan_ips(...)` which runs nmap via `asyncio.create_subprocess_exec`. `POST /scan` is **synchronous** — it blocks the calling HTTP client for the entire nmap duration (up to 300s default). Use `POST /api/v1/scan/async` for non-blocking scans. With gunicorn workers > 1, the synchronous endpoint will quickly exhaust worker capacity.

**Fix:** Add a background task queue (e.g., Celery, arq, or a simple asyncio queue with worker processes) so `/scan` returns a job ID immediately.

#### 2. JWT Stored in localStorage (dashboard/src/api.ts:17)
```typescript
localStorage.setItem('ns-lite-token', token)
```
localStorage is accessible to any JS on the page. An XSS bug (even from `'unsafe-inline'` in CSP) exfiltrates the token. Should use `httpOnly` cookies instead.

**Fix:** Switch to httpOnly secure cookies for token storage, or use a service-worker-based token vault.

### HIGH

#### 3. Upload Reads Full File Before Size Check (api.py:546-548)
```python
content = await file.read()          # reads ALL into memory first
if len(content) > MAX_UPLOAD_BYTES:  # then checks size
    raise HTTPException(status_code=413, ...)
```
A 1GB upload still allocates 1GB of memory before being rejected. The size check must happen *during* the read, not after.

**Fix:** Stream the upload in chunks and abort when the limit is exceeded, or use `file.read(MAX_UPLOAD_BYTES + 1)` and check length.

#### 4. Rate Limiter Has 3 Bugs (main.py:36-55)

**Bug A — In-memory per-worker state:** With `workers > 1` via gunicorn, each worker has its own `_requests` dict. A 120 req/min limit becomes `120 * workers` effective rate.

**Bug B — Health check rate-limited:** The `/health` endpoint goes through the rate limiter. If a load balancer or monitoring system pings `/health` from a single IP, it can get 429'd.

**Bug C — Memory leak:** `_requests` defaultdict grows unbounded. Old IPs are pruned only on their next request, but IPs that never return stay forever. With enough unique client IPs, this leaks memory.

**Fix:** Use Redis-backed rate limiting (e.g., `slowapi`), exclude `/health` from rate limiting, and add TTL-based cleanup.

#### 5. `ipaddress` Import Removed But Still Used — Runtime Crash (cli.py:2-3, 60)
```python
# Line 2-3: ipaddress was removed from imports
# Line 60: still references it
ipaddress.IPv4Address(ip_str)
```
Running `ns-lite scan --ip 10.0.0.1` will crash with `NameError: name 'ipaddress' is not defined`. This was introduced in the hardening commit.

**Fix:** Add `import ipaddress` back to the top of cli.py.

### MEDIUM

#### 6. `updated_at` Not Set on Group Update (api.py:460)
The `update_group` endpoint modifies `miss_threshold`, `quarantine_hours`, and `description` but never sets `group.updated_at = utc_now()`. The `updated_at` field stays stale after edits.

**Fix:** Add `group.updated_at = utc_now()` before `session.add(group)`.

#### 7. Group Delete Cascade Uncertainty (api.py:492)
```python
session.delete(group)
session.commit()
```
SQLModel defines `cascade_delete=True` on the `Relationship` (models.py:37), but SQLAlchemy cascades depend on the relationship being loaded. If the `ips` relationship isn't eagerly loaded, the cascade may not fire, leaving orphaned `IPAddress` rows.

**Fix:** Eagerly load the relationship before delete: `session.refresh(group, ["ips"])` or explicitly delete IPs first.

#### 8. `asyncio.run()` in CLI Scan Command (cli.py:85)
```python
result = asyncio.run(scan_ips(target_ips, session, ...))
```
If the CLI is ever called from within an already-running event loop (e.g., from a test or another async context), this will fail with `RuntimeError: This event loop is already running`.

**Fix:** Use `asyncio.get_event_loop().run_until_complete()` with a fallback, or restructure to avoid nested loops.

#### 9. No WebSocket Test Coverage
84 tests exist but none cover the WS scan endpoint (api.py:573-652). This is a significant gap — the WS path has its own auth, input validation, and error handling that's completely untested.

**Fix:** Add tests using `httpx.AsyncClient` with `websocket_connect` or FastAPI's `TestClient.websocket`.

### LOW

#### 10. Redundant `import json as json_mod` (cli.py:241)
```python
import json as json_mod
```
This local re-import inside the `auth` command is unnecessary. `json` is already imported at the top of the file (line 2). The `json_mod` alias is used at line 249 — just use `json.loads()`.

**Fix:** Remove line 241, change `json_mod.loads` to `json.loads` at line 249.

#### 11. Static Files Mounted at `/` Swallows Future Routes (main.py:120)
```python
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="dashboard")
```
This catch-all mount is added after all API routes, so it works correctly today. But if someone adds a route after this mount, it will be silently swallowed by the static file handler.

**Fix:** Add a comment warning, or move static mounting into a more defensive pattern (e.g., mount at `/dashboard` and use a catch-all only for known SPA paths).

#### 12. CSP Allows `'unsafe-inline'` for Scripts (main.py:24)
```python
"script-src 'self' 'unsafe-inline'"
```
Weakens XSS protection. Vite builds can use hashed scripts to eliminate this.

**Fix:** Configure Vite to use `vite-plugin-csp` or generate nonce-based inline scripts.

#### 13. Lazy Imports Inside Function Bodies (api.py:198, 339, 636)
```python
from netscan_lite.scanner.service import scan_ips
```
The import is done lazily inside endpoint functions. This creates a circular-dependency smell and adds import overhead on every request.

**Fix:** Resolve the circular dependency properly and move imports to module level.

---

## FIXED — Items Resolved in Commit 2eb76e3

| # | Original Issue | Fix Applied | Verified |
|---|----------------|-------------|----------|
| 1 | LDAP injection (auth.py:40) | `_escape_ldap_value()` per RFC 4515 (auth.py:31-38) | Yes |
| 3 | Unparameterized scan = full DB sweep (api.py:192) | Returns 400 if no group/ips provided (api.py:192-193) | Yes |
| 7 | Token file perms (cli.py:266) | `chmod(0o600)` after write (cli.py:266) | Yes |
| 8 | nmap stderr leaks to clients (runner.py:128) | Logs detail, returns generic message (runner.py:127-128) | Yes |
| 9 | Raw exception in import (api.py:545) | Logs detail, returns generic message (api.py:561-563) | Yes |
| 10 | WS no input validation (api.py:579-596) | IPv4 validation added (api.py:610-618) | Yes |
| 11 | WS auth inconsistency (api.py:567-570) | Now checks `DEV_AUTH_ENABLED and DEBUG` (api.py:585) | Yes |
| 12 | `import uuid` inside functions (api.py:427,468) | Moved to module level (api.py:4) | Yes |
| 13 | Docker runs as root (Dockerfile) | Non-root user `ns-lite` with proper ownership (Dockerfile:28-38) | Yes |
| 14 | PostgreSQL port exposed (docker-compose.yml:11) | Port mapping removed (docker-compose.yml) | Yes |
| 15 | N+1 in groups-detail (api.py:396-416) | Batch count with `GROUP BY` (api.py:413-421) | Yes |
| 16 | N+1 in stats (api.py:356-388) | Single query with `CASE` (api.py:373-381) | Yes |
| 17 | Pagination loads all rows (api.py:264) | SQL `func.count()` with conditions (api.py:263-269) | Yes |
| 22 | alembic.ini hardcoded SQLite path | `sqlalchemy.url =` (blank), env.py overrides (alembic.ini:4) | Yes |
| 25 | Missing security headers | HSTS, Referrer-Policy, Permissions-Policy (main.py:27-32) | Yes |
| 26 | Frontend IP regex (Import.tsx:31) | Proper octet validation 0-255 (Import.tsx:31) | Yes |

---

## Summary

| Severity | Original Count | Fixed | Still Open |
|----------|---------------|-------|------------|
| CRITICAL | 6 | 3 | **3** (sync scan, JWT localStorage, upload memory*) |
| HIGH | 8 | 6 | **3** (upload memory, rate limiter bugs, ipaddress crash) |
| MEDIUM | 7 | 2 | **5** (asyncio.run, updated_at, cascade, no WS tests, rate limiter) |
| LOW | 9 | 2 | **7** |
| **Total** | **30** | **13** | **18** |

*Upload memory bug was partially addressed (size check added) but the check happens after full read, so it's still OOMable.

### Priority Order for Remaining Work

1. **Fix `ipaddress` NameError in cli.py** — crash bug, 1 line fix
2. **Fix upload streaming** — read with limit, not after full read
3. **Fix rate limiter** — exclude `/health`, add Redis backend or per-worker caveat, add TTL cleanup
4. ~~Plan async scan architecture~~ — DONE: `/api/v1/scan/async` + job queue implemented
5. **Move JWT to httpOnly cookies** — XSS token exfiltration risk
6. **Add WS test coverage** — untested auth + validation path
7. **Fix `updated_at` on group update** — 1 line fix
8. **Fix cascade delete** — eagerly load `ips` before group delete
9. **Fix `asyncio.run()` in CLI** — nested event loop crash
10. **Clean up low-priority items** — redundant imports, CSP, lazy imports
