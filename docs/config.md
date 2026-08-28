# Configuration

ns-lite is configured via environment variables or a `.env` file in your working directory.

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./ns-lite.db` | Database connection URL |
| `DEBUG` | `false` | Enable debug logging |
| `DEFAULT_MISS_THRESHOLD` | `3` | Consecutive misses before marking uncertain |
| `DEFAULT_QUARANTINE_HOURS` | `48` | Hours an IP must stay uncertain before becoming available |
| `NMAP_TIMEOUT_SECONDS` | `300` | Timeout per scan in seconds |
| `NMAP_TIMING_TEMPLATE` | `-T4` | Nmap timing template |
| `TOP_TCP_PORTS` | `80,443,22,445,3389,8080,8443,53` | Ports to scan when port scanning is enabled |

## Example .env

```bash
DATABASE_URL=sqlite:///./my-network.db
DEBUG=true
DEFAULT_MISS_THRESHOLD=5
DEFAULT_QUARANTINE_HOURS=24
```

## Per-group settings

Quarantine thresholds (`miss_threshold` and `quarantine_hours`) are configured
per-group, not globally. When you create a group (via import or API), it uses
the `DEFAULT_MISS_THRESHOLD` and `DEFAULT_QUARANTINE_HOURS` values. After that,
each group maintains its own settings.

This means your database servers can have a stricter quarantine (more misses,
longer wait) than your app servers — if you configure them differently after import.

## Database

By default, ns-lite uses a SQLite database file (`ns-lite.db`) in the current
directory. You can point it to any SQLModel-compatible database URL:

```bash
# PostgreSQL (if you need concurrent access)
DATABASE_URL=postgresql://user:pass@localhost/ns-lite

# Keep it simple
DATABASE_URL=sqlite:///./ns-lite.db
```

!!! note

    SQLite is fine for single-machine use. If you're running multiple ns-lite
    instances or need concurrent API access, consider PostgreSQL.
