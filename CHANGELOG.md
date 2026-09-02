# Changelog

All notable changes to ns-lite will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.2.0] - 2026-09-02

### Added

- **API versioning** — all endpoints now under `/api/v1/` prefix
- **CORS middleware** — configurable origins via `CORS_ORIGINS` env var
- **Background scan jobs** — `POST /api/v1/scan/async` returns job ID, poll with `GET /api/v1/scan/{job_id}`
- **Readiness probe** — `GET /health/ready` checks DB + nmap availability
- **Request ID middleware** — every request gets an `X-Request-ID` header (supports client-supplied IDs)
- **Structured logging** — JSON-compatible format with request ID context (`logging_config.py`)
- **Prometheus metrics** — optional `/metrics` endpoint via `ENABLE_METRICS=true`
- **systemd service** — `deploy/ns-lite.service` for bare metal deployment
- **Install script** — `deploy/install.sh` for one-command bare metal setup
- **Production Docker Compose** — `docker-compose.prod.yml` with security hardening
- **Production env template** — `.env.production` with documented settings

### Changed

- All API endpoints moved from `/api/` to `/api/v1/` (breaking change for existing API consumers)
- Rate limiter now documented as per-worker (use reverse proxy for global limits)

## [0.1.0] - 2026-08-28

### Added

- Initial release extracted from [NetScan](https://github.com/Salar-prog/netscan)
- CSV/XLSX IP import with group support and validation
- Targeted IP scanning with nmap (ARP, ICMP, TCP probes)
- Quarantine state machine (safe availability tracking)
- Per-group quarantine settings (miss threshold, quarantine hours)
- CLI interface (`ns-lite` command) with 7 commands
- FastAPI REST API with 15 endpoints + WebSocket
- React dashboard with real-time scan progress, IP list, group management, CSV import
- LDAP authentication with JWT tokens
- Reverse DNS hostname discovery
- JSON output for all CLI commands (`--json-output`)
- Multi-privilege scanning (root vs unprivileged)
- Port scanning with configurable top ports
- MAC address and vendor detection
- Security headers middleware (CSP, X-Content-Type-Options, X-Frame-Options)
- LIKE pattern escaping in search queries
- JWT secret persistence to `~/.ns-lite/jwt-secret`
- `DEV_AUTH_ENABLED` flag for explicit dev-mode opt-in
- Multi-stage Dockerfile with healthcheck
- MkDocs Material documentation site
- CI pipeline (lint + test across Python 3.10-3.13)

### Fixed

- Deduplicated port serialization logic (`ports_to_dicts` helper)
- Added scan error handling (TimeoutError, RuntimeError) in API and CLI
- Fixed group-scoped IP lookup to avoid cross-group collisions
- Stripped whitespace from IP strings before lookup
- Added `first_seen_at` to CLI status output
