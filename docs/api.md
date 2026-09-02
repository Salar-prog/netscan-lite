# API Reference

ns-lite exposes a REST API via FastAPI. Start the server with `ns-lite serve`.

```bash
ns-lite serve                          # http://localhost:8000
ns-lite serve --host 0.0.0.0 --port 9000  # custom bind
```

## Authentication

All API endpoints (except `/health` and `/token`) require a valid JWT token.

### Login

```
POST /token
Content-Type: application/x-www-form-urlencoded
```

| Field | Type | Description |
|-------|------|-------------|
| `username` | string | LDAP username |
| `password` | string | LDAP password |

```bash
curl -X POST http://localhost:8000/token \
  -d "username=jsmith&password=secret123"
```

Response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "username": "jsmith"
}
```

### Using the token

Include the token in the `Authorization` header for all subsequent requests:

```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  http://localhost:8000/api/v1/groups
```

### CLI authentication

```bash
# Login (stores token in ~/.ns-lite/token)
ns-lite auth --username jsmith

# Then use commands normally
ns-lite scan --group infra
ns-lite available --count 3
```

### LDAP mode vs dev mode

| `LDAP_ENABLED` | `DEV_AUTH_ENABLED` | Behavior |
|-----------------|-------------------|----------|
| `false` | `false` | All auth rejected (401). Locked down. |
| `false` | `true` | Dev mode — any token accepted. No LDAP needed. Startup warning logged. |
| `true` | any | Tokens validated against LDAP server. Requires LDAP connectivity. |

## Endpoints Overview

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/token` | Login and get JWT token |
| `GET` | `/health` | Health check (no auth required) |
| `GET` | `/health/ready` | Readiness probe (checks DB + nmap) |
| `GET` | `/api/v1/stats` | Dashboard overview stats |
| `GET` | `/api/v1/groups` | List all groups |
| `GET` | `/api/v1/groups-detail` | List groups with IP counts |
| `PUT` | `/api/v1/groups/{id}` | Update group settings |
| `DELETE` | `/api/v1/groups/{id}` | Delete group and its IPs |
| `GET` | `/api/v1/available` | Get available IPs |
| `GET` | `/api/v1/ips` | List IPs (paginated) |
| `GET` | `/api/v1/ips/{ip}` | Get IP status |
| `POST` | `/api/v1/ips/{ip}/scan` | Scan a single IP |
| `PUT` | `/api/v1/ips/{ip}/reserve` | Reserve or release an IP |
| `POST` | `/api/v1/scan` | Trigger synchronous scan |
| `POST` | `/api/v1/scan/async` | Trigger background scan (returns job ID) |
| `GET` | `/api/v1/scan/{job_id}` | Get background scan job status |
| `GET` | `/api/v1/scan-jobs` | List all scan jobs |
| `POST` | `/api/v1/import` | Import IPs from CSV/XLSX |
| `WS` | `/ws/scan` | Real-time scan progress |

---

## Health Check

```
GET /health
```

Use this for load balancer health checks or monitoring uptime.

```json
{"status": "ok"}
```

---

## List Groups

```
GET /api/v1/groups
```

Returns all groups with their quarantine settings. Use this to discover what groups exist before querying available IPs.

```json
[
  {
    "id": "a1b2c3d4-...",
    "name": "infra",
    "miss_threshold": 3,
    "quarantine_hours": 48
  },
  {
    "id": "e5f6g7h8-...",
    "name": "database",
    "miss_threshold": 5,
    "quarantine_hours": 72
  }
]
```

Each group has its own quarantine settings — your database servers can have stricter thresholds than your app servers.

---

## Get Available IPs

Returns IPs that have been quarantined long enough and are safe to provision.

```
GET /api/v1/available?group=infra&count=3
```

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `group` | string | all groups | Filter by group name |
| `count` | int | 1 | Number of IPs to return (max: 100) |

### Response

```json
{
  "available_ips": ["10.0.0.20", "10.0.0.25", "10.0.0.12"],
  "count": 3
}
```

### Examples

```bash
# Get 5 available database IPs
curl "http://localhost:8000/api/v1/available?group=database&count=5"

# Get any single available IP
curl "http://localhost:8000/api/v1/available?count=1"

# Get all available IPs (default: 1)
curl "http://localhost:8000/api/v1/available"
```

### Errors

| Status | Detail |
|--------|--------|
| `404` | `Group 'nonexistent' not found` |

---

## Get IP Status

Returns full status details for a single IP address.

```
GET /api/v1/ips/{ip}
```

### Response

```json
{
  "ip": "10.0.0.1",
  "status": "ACTIVE_DETECTED",
  "hostname": "gateway-01",
  "mac_address": "aa:bb:cc:dd:ee:ff",
  "mac_vendor": "Cisco Systems",
  "consecutive_misses": 0,
  "first_seen_at": "2026-08-28T10:00:00",
  "last_seen_at": "2026-08-28T12:00:00",
  "last_scanned_at": "2026-08-28T12:00:00"
}
```

### Status Values

| Status | Meaning |
|--------|---------|
| `ACTIVE_DETECTED` | IP responded to the last scan |
| `AVAILABLE_CANDIDATE` | Quarantine complete — safe to provision |
| `UNCERTAIN_FIREWALLED` | IP missed recent scans, in quarantine |
| `ASSIGNED_RESERVED` | IP is reserved and locked |

### Examples

```bash
curl http://localhost:8000/api/v1/ips/10.0.0.1
```

### Errors

| Status | Detail |
|--------|--------|
| `404` | `IP '10.0.0.99' not found` |

---

## Trigger Scan

Runs nmap against the specified IPs and updates their status in the database.

```
POST /api/v1/scan
Content-Type: application/json
```

### Request Body

| Field | Type | Description |
|-------|------|-------------|
| `group` | string? | Scan all IPs in this group |
| `ips` | string[]? | Scan these specific IPs |

You must provide either `group`, `ips`, or both (empty object scans all IPs).

### Response

```json
{
  "message": "Scanned 5 IP(s)",
  "scanned": 5,
  "active": 3,
  "uncertain": 1,
  "available": 1
}
```

### Examples

```bash
# Scan all IPs in a group
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{"group": "infra"}'

# Scan specific IPs
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{"ips": ["10.0.0.1", "10.0.0.5", "10.0.0.12"]}'

# Scan all IPs (no filter)
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Errors

| Status | Detail |
|--------|--------|
| `400` | `No IPs to scan` |
| `404` | `Group 'nonexistent' not found` |
| `502` | `Scan failed: Nmap scan timed out after 300 seconds for 50 targets` |
| `422` | Validation error (e.g., invalid IPv4 address) |

---

## Dashboard Stats

```
GET /api/v1/stats
```

Returns aggregate counts for the dashboard overview.

### Response

```json
{
  "total_ips": 42,
  "active": 28,
  "uncertain": 8,
  "available": 4,
  "reserved": 2,
  "groups": 3,
  "last_scan": "2026-08-28 12:00:00"
}
```

---

## List Groups (with IP counts)

```
GET /api/v1/groups-detail
```

Returns all groups with their IP counts. Used by the dashboard for the group table.

### Response

```json
[
  {
    "id": "a1b2c3d4-...",
    "name": "infra",
    "description": "Infrastructure servers",
    "miss_threshold": 3,
    "quarantine_hours": 48,
    "ip_count": 15
  }
]
```

---

## Update Group

```
PUT /api/v1/groups/{group_id}
Content-Type: application/json
```

Update quarantine settings for a group.

### Request Body

| Field | Type | Description |
|-------|------|-------------|
| `miss_threshold` | int? | Consecutive misses before uncertain |
| `quarantine_hours` | int? | Hours in UNCERTAIN before AVAILABLE |
| `description` | string? | Group description |

### Response

Returns the updated `GroupDetailResponse`.

### Errors

| Status | Detail |
|--------|--------|
| `400` | `Invalid group ID` |
| `404` | `Group '...' not found` |

---

## Delete Group

```
DELETE /api/v1/groups/{group_id}
```

Deletes a group and all its IPs. Returns `204 No Content` on success.

### Errors

| Status | Detail |
|--------|--------|
| `400` | `Invalid group ID` |
| `404` | `Group '...' not found` |

---

## List IPs

```
GET /api/v1/ips?group=infra&status=ACTIVE_DETECTED&search=gateway&page=1&page_size=25
```

Returns a paginated list of all IPs with optional filters.

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `group` | string | all | Filter by group name |
| `status` | string | all | Filter by IP status |
| `search` | string | | Search by IP or hostname |
| `page` | int | 1 | Page number |
| `page_size` | int | 25 | Results per page (max: 100) |

### Response

```json
{
  "ips": [
    {
      "ip": "10.0.0.1",
      "status": "ACTIVE_DETECTED",
      "hostname": "gateway-01",
      "mac_address": "aa:bb:cc:dd:ee:ff",
      "mac_vendor": "Cisco Systems",
      "group_name": "infra",
      "consecutive_misses": 0,
      "last_seen_at": "2026-08-28T12:00:00",
      "last_scanned_at": "2026-08-28T12:00:00"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 25
}
```

---

## Scan Single IP

```
POST /api/v1/ips/{ip_address}/scan
```

Scans a single IP and updates its status.

### Response

```json
{
  "message": "Scanned 1 IP(s)",
  "scanned": 1,
  "active": 1,
  "uncertain": 0,
  "available": 0
}
```

### Errors

| Status | Detail |
|--------|--------|
| `404` | `IP '...' not found` |
| `502` | `Scan failed: ...` |

---

## Reserve or Release IP

```
PUT /api/v1/ips/{ip_address}/reserve
Content-Type: application/json
```

Reserve or release an IP address.

### Request Body

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `ASSIGNED_RESERVED` to reserve, `AVAILABLE_CANDIDATE` to release |

### Response

```json
{
  "ip": "10.0.0.1",
  "status": "ASSIGNED_RESERVED",
  "message": "IP 10.0.0.1 is now ASSIGNED_RESERVED"
}
```

### Errors

| Status | Detail |
|--------|--------|
| `404` | `IP '...' not found` |
| `422` | `Status must be one of: ASSIGNED_RESERVED, AVAILABLE_CANDIDATE` |

---

## Import IPs

```
POST /api/v1/import?group=infra
Content-Type: multipart/form-data
```

Import IPs from a CSV or XLSX file.

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `group` | string | from file | Override group for all imported IPs |

### Request Body

| Field | Type | Description |
|-------|------|-------------|
| `file` | file | CSV or XLSX file |

### Response

```json
{
  "imported": 10,
  "skipped": 2,
  "errors": ["Invalid IPv4 address: not-an-ip"]
}
```

### Errors

| Status | Detail |
|--------|--------|
| `400` | `Only .csv and .xlsx files are supported` |

---

## WebSocket — Real-time Scan Progress

```
ws://localhost:8000/ws/scan?token=<jwt>
```

Connect via WebSocket for real-time scan progress. Authenticate via `token` query parameter.

### Client sends

```json
{"group": "infra"}
```

or

```json
{"ips": ["10.0.0.1", "10.0.0.5"]}
```

### Server sends

**Progress** (per IP):

```json
{"type": "progress", "ip": "10.0.0.1", "status": "scanning"}
{"type": "progress", "ip": "10.0.0.1", "status": "done", "result": "ACTIVE_DETECTED"}
```

**Complete:**

```json
{"type": "complete", "scanned": 5, "active": 3, "uncertain": 1, "available": 1}
```

**Error:**

```json
{"type": "error", "detail": "No IPs to scan"}
```

### Close codes

| Code | Reason |
|------|--------|
| `4001` | Invalid or expired token |

---

## Client Examples

=== "cURL"

    ```bash
    # Get a token (skip if LDAP_ENABLED=false and using dev mode)
    TOKEN=$(curl -s -X POST http://localhost:8000/token \
      -d "username=jsmith&password=secret123" | jq -r '.access_token')

    # Health check
    curl http://localhost:8000/health

    # List groups
    curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/groups | jq .

    # Get available IPs
    curl -H "Authorization: Bearer $TOKEN" \
      "http://localhost:8000/api/v1/available?group=infra&count=3" | jq .

    # Get IP status
    curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/ips/10.0.0.1 | jq .

    # Trigger scan
    curl -X POST http://localhost:8000/api/v1/scan \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"group": "infra"}' | jq .
    ```

=== "Python"

    ```python
    import requests

    BASE = "http://localhost:8000"

    # Get a token (skip if LDAP_ENABLED=false and using dev mode)
    resp = requests.post(f"{BASE}/token", data={"username": "jsmith", "password": "secret123"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Health check
    requests.get(f"{BASE}/health").json()
    # {'status': 'ok'}

    # List groups
    groups = requests.get(f"{BASE}/api/v1/groups", headers=headers).json()
    for g in groups:
        print(f"{g['name']}: threshold={g['miss_threshold']}, quarantine={g['quarantine_hours']}h")

    # Get available IPs
    resp = requests.get(f"{BASE}/api/v1/available", params={"group": "infra", "count": 3}, headers=headers)
    ips = resp.json()["available_ips"]
    print(f"Available: {ips}")

    # Get IP status
    ip_info = requests.get(f"{BASE}/api/v1/ips/10.0.0.1", headers=headers).json()
    print(f"Status: {ip_info['status']}, misses: {ip_info['consecutive_misses']}")

    # Trigger scan
    result = requests.post(f"{BASE}/api/v1/scan", json={"group": "infra"}, headers=headers).json()
    print(f"Scanned {result['scanned']}: {result['active']} active, {result['uncertain']} uncertain")
    ```

=== "JavaScript"

    ```javascript
    const BASE = "http://localhost:8000";

    // Get a token (skip if LDAP_ENABLED=false and using dev mode)
    const tokenResp = await fetch(`${BASE}/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "username=jsmith&password=secret123",
    });
    const { access_token } = await tokenResp.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    // Get available IPs
    const resp = await fetch(`${BASE}/api/v1/available?group=infra&count=3`, { headers });
    const { available_ips } = await resp.json();
    console.log("Available:", available_ips);

    // Trigger scan
    const result = await fetch(`${BASE}/api/v1/scan`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ group: "infra" }),
    }).then(r => r.json());
    console.log(`Scanned ${result.scanned}: ${result.active} active`);
    ```

=== "PowerShell"

    ```powershell
    $base = "http://localhost:8000"

    # Get a token (skip if LDAP_ENABLED=false and using dev mode)
    $tokenResp = Invoke-RestMethod "$base/token" -Method POST -Body "username=jsmith&password=secret123" -ContentType "application/x-www-form-urlencoded"
    $headers = @{ Authorization = "Bearer $($tokenResp.access_token)" }

    # Get available IPs
    $ips = Invoke-RestMethod "$base/api/v1/available?group=infra&count=3" -Headers $headers
    $ips.available_ips

    # Trigger scan
    $body = @{ group = "infra" } | ConvertTo-Json
    Invoke-RestMethod -Uri "$base/api/v1/scan" -Method POST -Body $body -ContentType "application/json" -Headers $headers
    ```

---

## Integration Examples

### Terraform

```hcl
data "http" "token" {
  url             = "http://ns-lite:8000/token"
  method          = "POST"
  request_headers = {
    "Content-Type" = "application/x-www-form-urlencoded"
  }
  request_body = "username=${var.ns_lite_user}&password=${var.ns_lite_pass}"
}

data "http" "available_ips" {
  url = "http://ns-lite:8000/api/v1/available?group=infra&count=3"
  request_headers = {
    "Authorization" = "Bearer ${jsondecode(data.http.token.body).access_token}"
  }
}

locals {
  ips = jsondecode(data.http.available_ips.body).available_ips
}

resource "aws_instance" "nodes" {
  count         = length(local.ips)
  ami           = "ami-..."
  instance_type = "t3.micro"
  private_ip    = local.ips[count.index]

  tags = {
    Name = "node-${count.index}"
    IP   = local.ips[count.index]
  }
}
```

### Ansible

```yaml
- name: Get token from ns-lite
  ansible.builtin.uri:
    url: "http://ns-lite:8000/token"
    method: POST
    body_format: form-urlencoded
    body:
      username: "{{ ns_lite_user }}"
      password: "{{ ns_lite_pass }}"
    status_code: 200
  register: token_resp

- name: Get available IPs from ns-lite
  ansible.builtin.uri:
    url: "http://ns-lite:8000/api/v1/available?group=database&count=2"
    headers:
      Authorization: "Bearer {{ token_resp.json.access_token }}"
    return_content: yes
  register: ns_lite

- name: Print available IPs
  ansible.builtin.debug:
    msg: "Available IPs: {{ ns_lite.content | from_json | json_query('available_ips') }}"
```

### CI/CD Pipeline

```yaml
# GitHub Actions example
- name: Get ns-lite token
  run: |
    TOKEN=$(curl -s -X POST http://ns-lite:8000/token \
      -d "username=${{ secrets.NS_LITE_USER }}&password=${{ secrets.NS_LITE_PASS }}" \
      | jq -r '.access_token')
    echo "NS_LITE_TOKEN=$TOKEN" >> $GITHUB_ENV

- name: Get available IPs
  run: |
    IPS=$(curl -s -H "Authorization: Bearer $NS_LITE_TOKEN" \
      "http://ns-lite:8000/api/v1/available?group=staging&count=2" \
      | jq -r '.available_ips[]')
    echo "IPS=$IPS" >> $GITHUB_ENV

- name: Trigger scan after deployment
  run: |
    curl -X POST http://ns-lite:8000/api/v1/scan \
      -H "Authorization: Bearer $NS_LITE_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"group": "staging"}'
```
