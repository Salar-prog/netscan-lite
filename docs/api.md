# API Reference

Start the server with `ns-lite serve`. Default: `http://localhost:8000`.

## Endpoints

### Health check

```
GET /health
```

```json
{"status": "ok"}
```

### List groups

```
GET /api/groups
```

```json
[
  {
    "name": "infra",
    "id": "...",
    "miss_threshold": 3,
    "quarantine_hours": 48
  }
]
```

### Get available IPs

```
GET /api/available?group=infra&count=3
```

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `group` | string | all | Filter by group name |
| `count` | int | 10 | Number of IPs to return |

```json
{
  "available_ips": ["10.0.0.20", "10.0.0.25", "10.0.0.12"]
}
```

### Get IP status

```
GET /api/ips/{ip}
```

```json
{
  "ip": "10.0.0.1",
  "hostname": "gateway-01",
  "status": "ACTIVE_DETECTED",
  "group": "infra",
  "mac_address": "aa:bb:cc:dd:ee:ff",
  "discovery_method": "ARP",
  "consecutive_misses": 0,
  "first_seen_at": "2026-08-28T10:00:00",
  "last_seen_at": "2026-08-28T12:00:00",
  "last_scanned_at": "2026-08-28T12:00:00"
}
```

### Trigger scan

```
POST /api/scan
Content-Type: application/json
```

```json
{"group": "infra"}
```

Or scan specific IPs:

```json
{"ips": ["10.0.0.1", "10.0.0.5"]}
```

Response:

```json
{
  "message": "Scanned 5 IP(s)",
  "scanned": 5,
  "active": 3,
  "uncertain": 1,
  "available": 1
}
```

## Terraform integration

```hcl
data "http" "available_ips" {
  url = "http://ns-lite:8000/api/available?group=infra&count=3"
}

locals {
  ips = jsondecode(data.http.available_ips.body).available_ips
}

resource "aws_instance" "nodes" {
  count         = length(local.ips)
  ami           = "ami-..."
  instance_type = "t3.micro"
  private_ip    = local.ips[count.index]
}
```
