"""Tests for API endpoints."""

from sqlmodel import Session

from netscan_lite.models import Group, IPAddress, IPStatus


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_list_groups_empty(client):
    resp = client.get("/api/groups")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_groups_with_data(db_engine, client):
    with Session(db_engine) as session:
        group = Group(name="infra", miss_threshold=3, quarantine_hours=48)
        session.add(group)
        session.commit()

    resp = client.get("/api/groups")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "infra"
    assert data[0]["miss_threshold"] == 3


def test_get_available_ips_empty(client):
    resp = client.get("/api/available")
    assert resp.status_code == 200
    assert resp.json()["available_ips"] == []
    assert resp.json()["count"] == 0


def test_get_available_ips_with_data(db_engine, client):
    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.flush()
        ip = IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.AVAILABLE_CANDIDATE)
        session.add(ip)
        session.commit()

    resp = client.get("/api/available?count=5")
    assert resp.status_code == 200
    assert resp.json()["available_ips"] == ["10.0.0.1"]
    assert resp.json()["count"] == 1


def test_get_available_ips_filter_by_group(db_engine, client):
    with Session(db_engine) as session:
        group_a = Group(name="group-a")
        group_b = Group(name="group-b")
        session.add(group_a)
        session.add(group_b)
        session.flush()
        session.add(IPAddress(group_id=group_a.id, ip="10.0.0.1", status=IPStatus.AVAILABLE_CANDIDATE))
        session.add(IPAddress(group_id=group_b.id, ip="10.0.0.2", status=IPStatus.AVAILABLE_CANDIDATE))
        session.commit()

    resp = client.get("/api/available?group=group-a&count=10")
    assert resp.status_code == 200
    assert resp.json()["available_ips"] == ["10.0.0.1"]


def test_get_available_ips_group_not_found(client):
    resp = client.get("/api/available?group=nonexistent")
    assert resp.status_code == 404


def test_get_ip_status(db_engine, client):
    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.flush()
        ip = IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.ACTIVE_DETECTED, hostname="web-01")
        session.add(ip)
        session.commit()

    resp = client.get("/api/ips/10.0.0.1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ip"] == "10.0.0.1"
    assert data["status"] == "ACTIVE_DETECTED"
    assert data["hostname"] == "web-01"


def test_get_ip_status_not_found(client):
    resp = client.get("/api/ips/10.0.0.99")
    assert resp.status_code == 404


def test_scan_no_ips(client):
    resp = client.post("/api/scan", json={})
    assert resp.status_code == 400


def test_scan_group_not_found(client):
    resp = client.post("/api/scan", json={"group": "nonexistent"})
    assert resp.status_code == 404
