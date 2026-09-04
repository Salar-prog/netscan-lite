"""Tests for API endpoints."""

from sqlmodel import Session

from netscan_lite.models import Group, IPAddress, IPStatus


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_health_ready(client):
    resp = client.get("/health/ready")
    data = resp.json()
    assert "checks" in data
    assert "database" in data["checks"]
    assert data["checks"]["database"] == "ok"
    # nmap may or may not be installed in test env
    assert "nmap" in data["checks"]


def test_list_groups_empty(client, auth_headers):
    resp = client.get("/api/v1/groups", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_groups_with_data(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra", miss_threshold=3, quarantine_hours=48)
        session.add(group)
        session.commit()

    resp = client.get("/api/v1/groups", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "infra"
    assert data[0]["miss_threshold"] == 3


def test_get_available_ips_empty(client, auth_headers):
    resp = client.get("/api/v1/available", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["available_ips"] == []
    assert resp.json()["count"] == 0


def test_get_available_ips_with_data(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.flush()
        ip = IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.AVAILABLE_CANDIDATE)
        session.add(ip)
        session.commit()

    resp = client.get("/api/v1/available?count=5", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["available_ips"] == ["10.0.0.1"]
    assert resp.json()["count"] == 1


def test_get_available_ips_filter_by_group(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group_a = Group(name="group-a")
        group_b = Group(name="group-b")
        session.add(group_a)
        session.add(group_b)
        session.flush()
        session.add(IPAddress(group_id=group_a.id, ip="10.0.0.1", status=IPStatus.AVAILABLE_CANDIDATE))
        session.add(IPAddress(group_id=group_b.id, ip="10.0.0.2", status=IPStatus.AVAILABLE_CANDIDATE))
        session.commit()

    resp = client.get("/api/v1/available?group=group-a&count=10", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["available_ips"] == ["10.0.0.1"]


def test_get_available_ips_group_not_found(client, auth_headers):
    resp = client.get("/api/v1/available?group=nonexistent", headers=auth_headers)
    assert resp.status_code == 404


def test_get_ip_status(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.flush()
        ip = IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.ACTIVE_DETECTED, hostname="web-01")
        session.add(ip)
        session.commit()

    resp = client.get("/api/v1/ips/10.0.0.1", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ip"] == "10.0.0.1"
    assert data["status"] == "ACTIVE_DETECTED"
    assert data["hostname"] == "web-01"


def test_get_ip_status_not_found(client, auth_headers):
    resp = client.get("/api/v1/ips/10.0.0.99", headers=auth_headers)
    assert resp.status_code == 404


def test_scan_no_ips(client, auth_headers):
    resp = client.post("/api/v1/scan", json={}, headers=auth_headers)
    assert resp.status_code == 400


def test_scan_group_not_found(client, auth_headers):
    resp = client.post("/api/v1/scan", json={"group": "nonexistent"}, headers=auth_headers)
    assert resp.status_code == 404


def test_unauthorized_without_token(client):
    resp = client.get("/api/v1/groups")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


def test_cors_headers_absent_by_default(client):
    resp = client.options(
        "/api/v1/groups",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in resp.headers


# ---------------------------------------------------------------------------
# Async scan jobs
# ---------------------------------------------------------------------------


def test_trigger_scan_async_no_ips(client, auth_headers):
    resp = client.post("/api/v1/scan/async", json={}, headers=auth_headers)
    assert resp.status_code == 400


def test_trigger_scan_async_group_not_found(client, auth_headers):
    resp = client.post("/api/v1/scan/async", json={"group": "nonexistent"}, headers=auth_headers)
    assert resp.status_code == 404


def test_get_scan_status_not_found(client, auth_headers):
    resp = client.get("/api/v1/scan/nonexistent-id", headers=auth_headers)
    assert resp.status_code == 404


def test_list_scan_jobs_empty(client, auth_headers):
    resp = client.get("/api/v1/scan-jobs", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Authorization — non-admin users get 403 on write endpoints
# ---------------------------------------------------------------------------


def test_non_admin_cannot_trigger_scan(client, db_engine, monkeypatch):
    from netscan_lite.config import settings

    monkeypatch.setattr(settings, "ADMIN_GROUPS", ["ns-lite-admins"])
    non_admin_headers = {"Authorization": "Bearer non-admin-token"}
    resp = client.post("/api/v1/scan", json={"ips": ["10.0.0.1"]}, headers=non_admin_headers)
    assert resp.status_code == 403
    assert "Admin access required" in resp.json()["detail"]


def test_non_admin_cannot_delete_group(client, db_engine, auth_headers, monkeypatch):
    from sqlmodel import Session

    from netscan_lite.config import settings
    from netscan_lite.models import Group

    monkeypatch.setattr(settings, "ADMIN_GROUPS", ["ns-lite-admins"])

    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.commit()
        group_id = str(group.id)

    non_admin_headers = {"Authorization": "Bearer non-admin-token"}
    resp = client.delete(f"/api/v1/groups/{group_id}", headers=non_admin_headers)
    assert resp.status_code == 403


def test_non_admin_cannot_reserve_ip(client, db_engine, monkeypatch):
    from netscan_lite.config import settings

    monkeypatch.setattr(settings, "ADMIN_GROUPS", ["ns-lite-admins"])
    non_admin_headers = {"Authorization": "Bearer non-admin-token"}
    resp = client.put("/api/v1/ips/10.0.0.1/reserve", json={"status": "ASSIGNED_RESERVED"}, headers=non_admin_headers)
    assert resp.status_code == 403


def test_non_admin_can_read(client, auth_headers):
    non_admin_headers = {"Authorization": "Bearer non-admin-token"}
    resp = client.get("/api/v1/groups", headers=non_admin_headers)
    assert resp.status_code == 200
