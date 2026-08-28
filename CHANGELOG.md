# Changelog

All notable changes to ns-lite will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-08-28

### Added

- Initial release extracted from [NetScan](https://github.com/Salar-prog/netscan)
- CSV/XLSX IP import with group support and validation
- Targeted IP scanning with nmap (ARP, ICMP, TCP probes)
- Quarantine state machine (safe availability tracking)
- Per-group quarantine settings (miss threshold, quarantine hours)
- CLI interface (`ns-lite` command) with all commands
- FastAPI REST API with 5 endpoints
- Reverse DNS hostname discovery
- JSON output for all CLI commands (`--json-output`)
- Multi-privilege scanning (root vs unprivileged)
- Port scanning with configurable top ports
- MAC address and vendor detection
- GitHub Pages documentation site

### Fixed

- Deduplicated port serialization logic (`ports_to_dicts` helper)
- Added scan error handling (TimeoutError, RuntimeError) in API and CLI
- Fixed group-scoped IP lookup to avoid cross-group collisions
- Stripped whitespace from IP strings before lookup
- Added `first_seen_at` to CLI status output
- Removed unused `RESERVED_TOGGLE` event type
