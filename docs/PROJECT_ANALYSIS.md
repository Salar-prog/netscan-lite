# ns-lite Project Analysis Report

## 1. Executive Summary

**ns-lite** is a lightweight IP discovery tool extracted from [NetScan](https://github.com/Salar-prog/netscan). It scans specific IP addresses using nmap, tracks their availability over time via a quarantine state machine, and provides both CLI and web dashboard interfaces. Version 0.1.0.

**Verdict**: Clean, complete v0.1.0 extraction. All advertised features implemented and working. 84 passing tests, ruff clean, dashboard builds. Security hardening (JWT persistence, dev auth guard, LIKE escaping, security headers) and Docker support added post-launch.

---

## 2. What It Is vs. What It Claims

| Claim | Status | Evidence |
|-------|--------|----------|
| CSV/XLSX import with group support | Delivered | `importer.py:58-129`, full validation, dedup, group override |
| Targeted scanning (all/group/specific IPs) | Delivered | `cli.py:47-93`, `api.py:175-212` |
| Hostname discovery via reverse DNS | Delivered | `runner.py:85` (`-R` flag), `runner.py:167-172` |
| Multi-probe detection (ARP, ICMP, TCP) | Delivered | `runner.py:77-99`, privilege-aware probe selection |
| Quarantine logic (two-factor release) | Delivered | `classifier.py:116-157`, both miss threshold AND time gate |
| Per-group quarantine settings | Delivered | `models.py:26-37`, each Group has own `miss_threshold` + `quarantine_hours` |
| Web dashboard with real-time scan | Delivered | React 19 + Tailwind 4, WebSocket at `api.py:560-631` |
| CLI + REST API | Delivered | 7 CLI commands, 15 API endpoints + health check |
| LDAP auth with JWT | Delivered | `auth.py`, search+bind + JWT tokens, persistent secret |
| JSON output for all commands | Delivered | `--json-output` flag on all CLI commands |
| Docker support | Delivered | Multi-stage `Dockerfile` with healthcheck |

**All claims backed by working code.**

---

## 3. Codebase Metrics

| Metric | Count |
|--------|-------|
| Python source (app) | 1,887 LOC across 10 files |
| Python source (tests) | 1,349 LOC across 8 files |
| React/TypeScript source | 1,705 LOC across 12 files |
| Total source | ~4,940 LOC |
| Git commits | 21 |
| Test files | 8 |
| Total tests | 84 |
| Passing tests | 84 |
| Dependencies (core) | 8 (click, fastapi, uvicorn, sqlmodel, pydantic-settings, ldap3, PyJWT, python-multipart) |
| Dependencies (optional) | 4 (openpyxl, pytest, httpx, mkdocs-material) |

---

## 4. Architecture Analysis

### 4.1 Python Backend

```
netscan_lite/
  scanner/
    runner.py       (232 LOC) — nmap wrapper, XML parsing, privilege detection
    classifier.py   (173 LOC) — quarantine state machine (core domain logic)
    service.py      (116 LOC) — scan orchestration, shared by CLI + API
  models.py          (60 LOC) — SQLModel tables: Group, IPAddress
  db.py              (32 LOC) — engine, WAL pragma, session factory
  config.py          (72 LOC) — pydantic-settings, JWT secret persistence, env vars
  auth.py           (123 LOC) — LDAP search+bind, JWT creation/validation, dev auth guard
  importer.py       (129 LOC) — CSV/XLSX parser with validation
  cli.py            (246 LOC) — 7 Click commands
  api.py            (631 LOC) — 15 FastAPI endpoints + WebSocket + LIKE escaping
  main.py            (73 LOC) — app factory, security headers middleware, static file mounting
```

**Strengths:**
- Clean separation: scanner logic in `scanner/`, shared orchestration in `service.py`
- CLI and API share the same scan path — no duplicated logic
- Classifier is a pure function (input → outcome) — highly testable
- SQLModel with proper UniqueConstraint on `(ip, group_id)`
- SQLite WAL mode + busy_timeout for concurrency
- JWT secret auto-generated once, persisted to `~/.ns-lite/jwt-secret`, survives restarts
- Security headers middleware on all responses (CSP, X-Content-Type-Options, X-Frame-Options)

**Weaknesses:**
- `api.py` at 631 lines could be split into route modules — fine at v0.1.0
- No database migrations (uses `create_all`) — fine for SQLite, would need Alembic for PostgreSQL
- `POST /scan` endpoint is synchronous — blocks until all nmap scans complete. Fine for small batches, would need background jobs for large scans.

### 4.2 React Dashboard

```
dashboard/src/
  api.ts            (226 LOC) — fetch wrapper, WebSocket client, auth helpers
  types.ts          (108 LOC) — TypeScript interfaces
  App.tsx            (41 LOC) — router with protected routes
  main.tsx           (10 LOC) — React entry point
  components/
    Login.tsx        (79 LOC) — login form
    Layout.tsx       (99 LOC) — sidebar nav + outlet
    Dashboard.tsx   (109 LOC) — stats cards + groups table
    IpList.tsx      (183 LOC) — paginated IP table with filters/search
    IpDetail.tsx    (178 LOC) — IP detail view, scan/reserve actions, port table
    GroupManager.tsx (156 LOC) — group CRUD with edit/delete modals
    ScanTrigger.tsx (254 LOC) — scan UI with WebSocket progress, elapsed timer, cancel
    Import.tsx      (262 LOC) — drag-drop CSV/XLSX import with preview
```

**Strengths:**
- Minimal dependencies: React 19 + react-router-dom + Tailwind 4 (no Redux, no state library)
- WebSocket scan progress with live results feed, elapsed timer, cancel button
- CSV preview with client-side validation before upload
- Proper error handling on every API call
- Protected routes via `isAuthenticated()` check
- `apiFetch` wrapper handles 401 → redirect to login automatically

**Weaknesses:**
- No auto-refresh on dashboard (stale data until manual navigation)
- `statusBadge` map duplicated in `IpList.tsx:6-11` and `IpDetail.tsx:6-11`
- `parseCSV` in `Import.tsx:31` does basic regex validation (`/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/`) — doesn't check octet ranges (allows `999.999.999.999`)
- `IpList.tsx:50` — `fetchIPs()` closure captures stale `search` state on filter changes (functionally works because search is submitted via button, not auto-triggered)

### 4.3 Database Schema

- **Group**: id (UUID), name (unique, indexed), description, miss_threshold, quarantine_hours, created_at, updated_at
- **IPAddress**: id (UUID), group_id (FK, indexed), ip (indexed), status (indexed), hostname (indexed), mac_address (indexed), mac_vendor, open_ports (JSON), discovery_method, consecutive_misses, first_seen_at, last_seen_at, last_scanned_at, created_at, updated_at
- **Unique constraint**: `(ip, group_id)` — same IP can exist in multiple groups

Clean schema. JSON column for `open_ports` is appropriate for SQLite at this scale. No dead fields — `custom_metadata`, `EventType`, `raw_extra` were removed in the launch prep cleanup.

---

## 5. What It Lacks

### 5.1 Issues Fixed (in launch prep commit `c49bccc`)

| Issue | Fix |
|-------|-----|
| JWT secret regenerated on restart | Auto-generated once, persisted to `~/.ns-lite/jwt-secret` |
| Dev mode auth too permissive | `DEV_AUTH_ENABLED=false` by default; must explicitly opt in |
| SQL LIKE injection | `_escape_like()` escapes `%` and `_` in user search input |
| No security headers | `SecurityHeadersMiddleware` adds CSP, X-Content-Type-Options, X-Frame-Options |
| No Dockerfile | Multi-stage build with nmap, healthcheck, exposed port 8000 |
| Dead code (`EventType`, `custom_metadata`, `raw_extra`) | Removed from models, classifier, runner, importer |
| Stale `cidr.py` reference in AGENTS.md | Removed |
| Stale `ScanJob` reference in AGENTS.md | Removed |

### 5.2 Remaining Minor Issues

| Issue | Severity | Details |
|-------|----------|---------|
| No auto-refresh on dashboard | Low | User must navigate away and back to see updated stats |
| `statusBadge` duplicated | Low | Color map in `IpList.tsx:6-11` and `IpDetail.tsx:6-11` — minor DRY violation |
| CSV regex allows invalid octets | Low | `Import.tsx:31` matches `999.999.999.999` — server-side validation catches this |
| No integration test for full scan cycle | Low | Import → scan → classify → available not tested end-to-end |
| No WebSocket integration test | Low | WS protocol tested only manually |
| `POST /scan` is synchronous | Low | Blocks until all scans complete. Fine for current scale. |

### 5.3 Missing Features (by design, not gaps)

- **No scheduled scans** — by design ("No scheduler — scans are on-demand only")
- **No IPv6 support** — deliberate scope (IPv4 only)
- **No API versioning** — fine for v0.1.0
- **No rate limiting** — internal tool, not public-facing
- **No database migrations** — SQLite + `create_all` is sufficient
- **No ScanJob persistence** — scans return summary dicts, not persisted records. Fine for on-demand use.

---

## 6. Security Analysis

| Area | Finding | Severity |
|------|---------|----------|
| **JWT secret** | Auto-generated once, persisted to `~/.ns-lite/jwt-secret` (chmod 0o600). Survives restarts. Can override via `JWT_SECRET_KEY` env var. | None (fixed) |
| **Dev mode auth** | `LDAP_ENABLED=false` + `DEV_AUTH_ENABLED=false` → 401 on all auth. Must explicitly enable dev mode. Startup warning logged. | None (fixed) |
| **Command injection** | Nmap args are built from config constants, not user input. Safe. | None |
| **SQL injection** | SQLModel parameterized queries used throughout. LIKE pattern escaped via `_escape_like()`. | None (fixed) |
| **File uploads** | Temp file created, written, processed, deleted in finally block (`api.py:535-552`). Safe. | None |
| **Static file mount** | `StaticFiles(directory=..., html=True)` at root `/`. FastAPI routes registered first take priority. | Low |
| **LDAP credentials** | Stored in env vars / `.env` file. `.env` is in `.gitignore` and not tracked. | None |
| **WebSocket auth** | Token passed as query param (`?token=...`). Visible in server logs and browser history. Acceptable for internal tool. | Low |
| **Security headers** | CSP, X-Content-Type-Options: nosniff, X-Frame-Options: DENY on all responses. | None |

**Overall security posture**: Appropriate for an internal network scanning tool. Not designed for public internet exposure.

---

## 7. Test Coverage Analysis

| Test File | Tests | What It Covers |
|-----------|-------|----------------|
| `test_basic.py` | 5 | Group/IP CRUD, status transitions, CSV/XLSX import |
| `test_classifier.py` | 12 | Full quarantine state machine: reserved lock, positive/negative probes, threshold gates, per-group settings |
| `test_scanner_runner.py` | 7 | Nmap XML parsing, host up/down, multi-host, ports, discovery method mapping, malformed XML |
| `test_cli.py` | 11 | CLI commands: help, groups, status, available, import, JSON output, scan, serve, auth |
| `test_api.py` | 12 | API endpoints: health, groups, available, IP status, scan validation, auth, token |
| `test_dashboard_api.py` | 27 | Dashboard endpoints: stats, groups-detail, CRUD, reserve/release, import, IP list pagination/filtering, search |
| `test_importer.py` | 10 | Import edge cases: invalid IPs, missing columns, duplicates, group override, empty files |

**Total**: 84 tests, all passing.

**Test infrastructure** (`conftest.py`):
- In-memory SQLite via `StaticPool` for isolation
- `db_engine` fixture shared between client and session for API tests
- `_isolate_cli_db` autouse fixture redirects CLI engine to in-memory DB per test
- `DEV_AUTH_ENABLED` monkeypatched to `True` for all tests
- `auth_headers` fixture provides `{"Authorization": "Bearer test-token"}`

**Coverage strengths:**
- Classifier (core domain logic) thoroughly tested with 12 tests covering all state transitions
- API error paths tested (404, 400, 401, 422)
- Import edge cases well-covered
- Dashboard API tests cover pagination, filtering, search, CRUD

**Coverage gaps:**
- No integration test for full scan cycle (import → scan → classify → available)
- No WebSocket integration test
- No test for the `auth` CLI command against a real running server
- No test for concurrent scan requests
- No test for LDAP authentication path (only dev mode tested)

---

## 8. Documentation Quality

| Document | Quality | Notes |
|----------|---------|-------|
| **README.md** | Excellent | Dashboard feature, 15 API endpoints, Terraform/Ansible examples, CLI reference, configuration |
| **AGENTS.md** | Comprehensive | Architecture map, domain invariants, code conventions, testing guidance. All stale refs cleaned. |
| **CONTRIBUTING.md** | Good | Setup, project structure, testing, code style, PR process |
| **CHANGELOG.md** | Clean | Follows Keep a Changelog format, matches git history |
| **MkDocs site** | Full | 7 pages (Home, Install, Quickstart, Dashboard, CLI, API, Config) deployed to GitHub Pages |
| **Dashboard plan** | Detailed | `docs/plans/dashboard-plan.md` — phased implementation plan |
| **Launch prep plan** | Detailed | `docs/plans/launch-prep-plan.md` — security fixes, Dockerfile, dead code removal |
| **CI workflows** | Present | `ci.yml` (lint + test across Python 3.10-3.13), `docs.yml` (MkDocs deploy to GitHub Pages) |
| **GitHub templates** | Present | Issue templates (bug report, feature request), PR template with checklist |
| **`.env.example`** | Complete | All config vars documented with defaults, JWT persistence noted |

**Remaining documentation gaps:**
- No ADRs for key choices (SQLite vs PostgreSQL, SQLModel vs SQLAlchemy)
- No runbook for production deployment

---

## 9. Development Process Assessment

### 9.1 Git History (21 commits)

```
c49bccc fix: launch prep — security hardening, dead code removal, Dockerfile
c24d409 docs: add dashboard documentation, update all pages
ec1c2ae feat(dashboard): Phase 4 — interactive scan + import polish
6de4a4b feat(dashboard): Phase 3 — full IP list, enhanced screens
de99759 feat(dashboard): Phase 2 — React scaffold + all screens
9f1a4e5 feat(dashboard): Phase 1 — backend foundation
6139fa6 docs: update README and AGENTS for LDAP auth
ad31152 docs: update all docs for LDAP auth feature
7abe693 feat: add LDAP authentication with JWT tokens
a355a2c docs: overhaul site docs — comprehensive API reference
951707f docs: overhaul all repo docs — rich API reference
303dc11 docs: redesign landing page with polished UI
cd1518f docs: add MkDocs Material site with marketing landing page
aedce2f chore: fix ruff formatting, add CI badges to README
479c8c1 chore: add GitHub repo structure — CI, issue templates, PR template
dfd50c0 fix: review cleanup — deduplicate port serialization, add scan error handling
3aa206e Merge pull request #1 from Salar-prog/fix/review-cleanup
1b3146b fix: remove dead code, add unique constraint, fix async blocking
5256772 fix: fix broken scanner subsystem, deduplicate scan logic, add comprehensive tests
c301e05 chore: add project files, tests, and gitignore
f8e823d feat: initial extraction from netscan
```

### 9.2 Assessment

**Was it planned?** Yes. The commit history shows deliberate sequencing:
1. Extract and stabilize (commits 1-5)
2. Clean up and add CI scaffolding (commits 6-8)
3. Documentation (commits 9-13)
4. Feature additions — LDAP auth (commit 14)
5. Dashboard in 4 phases (commits 15-18)
6. Final docs (commit 19)
7. Launch prep security/ops fixes (commit 20)

**Did development fall behind?** No. All advertised features are implemented and working. CI workflows run lint/test across Python 3.10-3.13 on push/PR.

**Was it over-engineered?** No — slightly under-engineered if anything:
- No database migrations (fine for SQLite)
- No API versioning
- No rate limiting
- No health check for nmap availability
- No graceful shutdown handling beyond uvicorn defaults

---

## 10. Over-Engineering Assessment

**Verdict: Not over-engineered. Proportionate to the problem.**

| Component | LOC | Assessment |
|-----------|-----|------------|
| Scanner (runner + classifier + service) | 521 | Justified — core domain logic, privilege detection, XML parsing, state machine |
| API + Auth | 754 | Justified — 15 endpoints + WebSocket + LDAP + JWT + security headers |
| CLI | 246 | Justified — 7 commands with JSON output |
| Models + DB + Config | 164 | Minimal — just what's needed, JWT secret persistence |
| Importer | 129 | Justified — CSV + XLSX with validation |
| Dashboard | 1,705 | Justified — 8 screens with real-time scan, drag-drop import, pagination |

**What was removed (correctly):**
- `custom_metadata` field on IPAddress — never read anywhere
- `EventType` enum — assigned in classifier but never stored or queried
- `raw_extra` field on `HostProbeResult` — populated but never used downstream
- `cidr.py` — broken imports, dead code

**What would be premature to add:**
- Database migrations (Alembic) — SQLite + `create_all` is fine
- API versioning — single consumer (the dashboard)
- Caching layer — on-demand scans, not high-throughput
- Message queue for scan jobs — single-node tool

---

## 11. Summary

### Strengths
1. Clean, readable code with consistent style
2. Core domain logic (quarantine state machine) is correct and well-tested
3. All advertised features are implemented
4. Comprehensive documentation (README, AGENTS.md, MkDocs site)
5. 84 passing tests covering critical paths
6. Minimal dependencies, no unnecessary abstractions
7. Feature-branch workflow, logical commit history
8. Security hardened: persistent JWT secret, dev auth guard, LIKE escaping, security headers

### Weaknesses
1. Minor code duplication in React components (`statusBadge` map)
2. No auto-refresh on dashboard
3. No integration test for full scan cycle
4. `POST /scan` blocks until all scans complete

### Recommendation
Production-ready for its scope as an internal network scanning tool. The remaining issues are polish for v0.2.0+.
