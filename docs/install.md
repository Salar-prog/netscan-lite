# Installation

## Requirements

- Python 3.10+
- [nmap](https://nmap.org/) installed and in your PATH

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
    pip install -e ".[xlsx,test]"
    ```

## nmap setup

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

!!! tip "Privileges"

    For ARP and ICMP scanning, run as root or with `CAP_NET_RAW`:

    ```bash
    sudo ns-lite scan --group infra
    ```

    Without privileges, ns-lite falls back to TCP connect scans — still works,
    just less stealthy.

## Verify installation

```bash
ns-lite --version
nmap --version
```
