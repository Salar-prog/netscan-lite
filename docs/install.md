# Installation

## Requirements

- Python 3.10+
- [nmap](https://nmap.org/) installed and in your PATH
- [ldap3](https://pypi.org/project/ldap3/) and PyJWT (included with ns-lite)

=== "pip"

    ```bash
    pip install "netscan-lite[xlsx]"
    ```

    This installs ns-lite with XLSX support (openpyxl).

=== "pip (no xlsx)"

    ```bash
    pip install netscan-lite
    ```

    CSV only, no spreadsheet support.

=== "from source"

    ```bash
    git clone https://github.com/Salar-prog/netscan-lite.git
    cd netscan-lite
    pip install -e ".[xlsx,test,docs]"
    ```

    Installs everything: XLSX support, test dependencies, and MkDocs for docs.

## Dashboard Build (optional)

The React dashboard is pre-built in the `netscan_lite/static/` directory. To rebuild it from source:

```bash
cd netscan_lite/dashboard
npm install
npm run build
```

This outputs to `netscan_lite/static/` which is served automatically by `ns-lite serve`.

!!! note

    The dashboard build requires Node.js 18+. The pre-built files are included in the PyPI package.

## nmap Setup

ns-lite uses nmap for network scanning. Install it for your platform:

=== "Debian/Ubuntu"

    ```bash
    sudo apt update && sudo apt install nmap
    ```

=== "RHEL/Fedora"

    ```bash
    sudo dnf install nmap
    ```

=== "macOS"

    ```bash
    brew install nmap
    ```

=== "Windows"

    Download from [nmap.org/download](https://nmap.org/download.html).

## Privileges

!!! tip "Running as root"

    For ARP and ICMP scanning, run as root or with `CAP_NET_RAW`:

    ```bash
    sudo ns-lite scan --group infra
    ```

    Without privileges, ns-lite falls back to TCP connect scans — still works, just less stealthy.

| Privilege | Probes Available |
|-----------|------------------|
| Root / CAP_NET_RAW | ARP, ICMP echo, ICMP timestamp, TCP SYN |
| Unprivileged | ICMP echo, TCP ACK, TCP connect |

## Verify Installation

```bash
ns-lite --version
nmap --version
```

## Docker (optional)

```bash
# Build
docker build -t ns-lite .

# Run
docker run --rm ns-lite scan --group infra
```

!!! note

    Docker requires `--net=host` or `--privileged` for ARP/ICMP scanning.
