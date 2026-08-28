# ns-lite

<div class="hero" markdown>

## Lightweight IP discovery<br>with quarantine logic

Stop guessing which IPs are free. ns-lite scans your network, tracks availability
over time, and won't release an IP just because a firewall dropped a ping.

[Get Started](install.md){ .md-button .md-button--primary }
[Quick Start](quickstart.md){ .md-button }
[GitHub](https://github.com/Salar-prog/netscan-lite){ .md-button }

</div>

---

## Why ns-lite?

<div class="feature-grid" markdown>

<div class="feature-card" markdown>

### Safe quarantine logic

No false frees. An IP must miss multiple scans AND survive a quarantine period
before it's marked available. Firewall flaps won't cost you.

</div>

<div class="feature-card" markdown>

### Multi-probe detection

ARP, ICMP echo, ICMP timestamp, TCP SYN — uses whatever your privilege level
allows. Records which probe actually worked.

</div>

<div class="feature-card" markdown>

### Group-based organization

Separate your infra, database, and app IPs. Each group has its own quarantine
thresholds and settings.

</div>

<div class="feature-card" markdown>

### CSV/XLSX import

Drop your IPs in a spreadsheet, import them. Hostname and group columns are
optional — ns-lite handles the rest.

</div>

<div class="feature-card" markdown>

### CLI + REST API

Use it from the terminal or wire it into Terraform. JSON output for automation,
REST API for integration.

</div>

<div class="feature-card" markdown>

### Zero bloat

No dashboard, no scheduler, no database server. SQLite, nmap, and a CLI. That's it.

</div>

</div>

---

## See it in action

```bash
# Import your IPs
ns-lite import --file datacenter-ips.csv

# Scan them
ns-lite scan --group infra

# Get available IPs for provisioning
ns-lite available --group infra --count 3
```

---

## How quarantine works

<div style="text-align: center" markdown>

| Step | What happens | Status |
|------|-------------|--------|
| 1 | IP responds to scan | `ACTIVE_DETECTED` |
| 2 | IP stops responding | `UNCERTAIN_FIREWALLED` |
| 3 | Misses keep coming | `consecutive_misses` increments |
| 4 | Threshold + time met | `AVAILABLE_CANDIDATE` |

</div>

This two-factor approach (miss count **and** elapsed time) prevents premature
reclaiming of IPs that are temporarily unreachable due to firewalls, maintenance,
or network issues.
