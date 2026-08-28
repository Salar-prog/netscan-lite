# Changelog

All notable changes to ns-lite will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-08-28

### Added

- Initial release extracted from [NetScan](https://github.com/Salar-prog/netscan)
- CSV/XLSX IP import with group support
- Targeted IP scanning with nmap (ARP, ICMP, TCP probes)
- Quarantine state machine (safe availability tracking)
- Per-group quarantine settings (miss threshold, quarantine hours)
- CLI interface (`ns-lite` command)
- FastAPI REST API
- Reverse DNS hostname discovery
- JSON output for Terraform integration
