<div class="hero" markdown>

## Lightweight IP discovery<br>with quarantine logic

Stop guessing which IPs are free. ns-lite scans your network, tracks availability
over time, and won't release an IP just because a firewall dropped a ping.

<div class="cta-buttons" markdown>

[Get Started](install.md){ .md-button .md-button--primary }
[Quick Start](quickstart.md){ .md-button }
[GitHub](https://github.com/Salar-prog/netscan-lite){ .md-button }

</div>

</div>

---

<div class="stats-bar" markdown>

<div class="stat-item" markdown>

<span class="stat-number">3</span>
<span class="stat-label">Commands</span>

</div>

<div class="stat-item" markdown>

<span class="stat-number">0</span>
<span class="stat-label">Downtime</span>

</div>

<div class="stat-item" markdown>

<span class="stat-number">84</span>
<span class="stat-label">Tests</span>

</div>

<div class="stat-item" markdown>

<span class="stat-number">MIT</span>
<span class="stat-label">License</span>

</div>

</div>

---

## Why ns-lite?

<div class="feature-grid" markdown>

<div class="feature-card" markdown>

<span class="card-icon">:material-shield-lock-outline:</span>

### Safe quarantine logic

No false frees. An IP must miss multiple scans **and** survive a quarantine
period before it's marked available. Firewall flaps won't cost you.

</div>

<div class="feature-card" markdown>

<span class="card-icon">:material雷达屏幕:</span>

### Multi-probe detection

ARP, ICMP echo, ICMP timestamp, TCP SYN — uses whatever your privilege level
allows. Records which probe actually worked.

</div>

<div class="feature-card" markdown>

<span class="card-icon">:material-folder-outline:</span>

### Group-based organization

Separate your infra, database, and app IPs. Each group has its own quarantine
thresholds and settings.

</div>

<div class="feature-card" markdown>

<span class="card-icon">:material-shield-lock-outline:</span>

### LDAP authentication

Token-based API auth backed by LDAP. CLI stores tokens automatically. Dev mode
skips LDAP entirely — no server needed for local work.

</div>

<div class="feature-card" markdown>

<span class="card-icon">:material-file-delimited-outline:</span>

### CSV/XLSX import

Drop your IPs in a spreadsheet, import them. Hostname and group columns are
optional — ns-lite handles the rest.

</div>

<div class="feature-card" markdown>

<span class="card-icon">:material-api:</span>

### CLI + REST API

Use it from the terminal or wire it into Terraform. JSON output for automation,
REST API for integration.

</div>

<div class="feature-card" markdown>

<span class="card-icon">:material-feather:</span>

### Zero bloat

No scheduler, no database server. SQLite, nmap, and a CLI. The React dashboard
is optional — use it or stick to the API.

</div>

</div>

---

## See it in action

<div class="code-showcase" markdown>

<div class="code-header" markdown>

:material-console: Terminal

</div>

```bash
# Import your IPs
ns-lite import --file datacenter-ips.csv

# Scan them
ns-lite scan --group infra

# Get available IPs for provisioning
ns-lite available --group infra --count 3

# API auth (optional, for API access)
ns-lite auth --username jsmith
```

</div>

---

## How quarantine works

<div class="quarantine-flow" markdown>

<div class="flow-step" markdown>

<span class="step-num">1</span>

IP responds to scan

<span class="step-status">ACTIVE_DETECTED</span>

<span class="step-arrow">→</span>

</div>

<div class="flow-step" markdown>

<span class="step-num">2</span>

IP stops responding

<span class="step-status">UNCERTAIN_FIREWALLED</span>

<span class="step-arrow">→</span>

</div>

<div class="flow-step" markdown>

<span class="step-num">3</span>

Misses keep coming

<span class="step-status">consecutive_misses++</span>

<span class="step-arrow">→</span>

</div>

<div class="flow-step" markdown>

<span class="step-num">4</span>

Threshold + time met

<span class="step-status">AVAILABLE_CANDIDATE</span>

</div>

</div>

This two-factor approach (miss count **and** elapsed time) prevents premature
reclaiming of IPs that are temporarily unreachable due to firewalls, maintenance,
or network issues.

---

## Built for infrastructure teams

<div class="feature-grid" markdown>

<div class="feature-card" markdown>

### Terraform integration

Query available IPs directly from your Terraform workflows.

```hcl
data "http" "available_ips" {
  url = "http://ns-lite:8000/api/v1/available?group=infra&count=3"
}
```

</div>

<div class="feature-card" markdown>

### Per-group quarantine

Different thresholds for different workloads. Database servers get
stricter quarantine than app servers.

</div>

<div class="feature-card" markdown>

### Multi-privilege scanning

Works with or without root. Adapts probe types based on what's
available — ARP when privileged, TCP connect when not.

</div>

</div>
