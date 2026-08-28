"""Tests for dashboard API endpoints (stats, import, groups CRUD, reserve)."""

import io
import uuid

from sqlmodel import Session, select

from netscan_lite.models import Group, IPAddress, IPStatus

# ---------------------------------------------------------------------------
# GET /api/stats
# ---------------------------------------------------------------------------


def test_stats_empty(client, auth_headers):
    resp = client.get("/api/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_ips"] == 0
    assert data["active"] == 0
    assert data["uncertain"] == 0
    assert data["available"] == 0
    assert data["reserved"] == 0
    assert data["groups"] == 0
    assert data["last_scan"] is None


def test_stats_with_data(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.flush()
        session.add(IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.ACTIVE_DETECTED))
        session.add(IPAddress(group_id=group.id, ip="10.0.0.2", status=IPStatus.UNCERTAIN_FIREWALLED))
        session.add(IPAddress(group_id=group.id, ip="10.0.0.3", status=IPStatus.AVAILABLE_CANDIDATE))
        session.add(IPAddress(group_id=group.id, ip="10.0.0.4", status=IPStatus.ASSIGNED_RESERVED))
        session.commit()

    resp = client.get("/api/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_ips"] == 4
    assert data["active"] == 1
    assert data["uncertain"] == 1
    assert data["available"] == 1
    assert data["reserved"] == 1
    assert data["groups"] == 1


# ---------------------------------------------------------------------------
# GET /api/groups-detail
# ---------------------------------------------------------------------------


def test_groups_detail_empty(client, auth_headers):
    resp = client.get("/api/groups-detail", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_groups_detail_with_counts(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra", miss_threshold=5, quarantine_hours=72)
        session.add(group)
        session.flush()
        session.add(IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.ACTIVE_DETECTED))
        session.add(IPAddress(group_id=group.id, ip="10.0.0.2", status=IPStatus.ACTIVE_DETECTED))
        session.commit()

    resp = client.get("/api/groups-detail", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "infra"
    assert data[0]["miss_threshold"] == 5
    assert data[0]["quarantine_hours"] == 72
    assert data[0]["ip_count"] == 2


# ---------------------------------------------------------------------------
# PUT /api/groups/{group_id}
# ---------------------------------------------------------------------------


def test_update_group(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra", miss_threshold=3, quarantine_hours=48)
        session.add(group)
        session.commit()
        group_id = str(group.id)

    resp = client.put(
        f"/api/groups/{group_id}",
        json={"miss_threshold": 10, "quarantine_hours": 120},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["miss_threshold"] == 10
    assert data["quarantine_hours"] == 120
    assert data["name"] == "infra"


def test_update_group_not_found(client, auth_headers):
    fake_id = str(uuid.uuid4())
    resp = client.put(
        f"/api/groups/{fake_id}",
        json={"miss_threshold": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_update_group_invalid_id(client, auth_headers):
    resp = client.put(
        "/api/groups/not-a-uuid",
        json={"miss_threshold": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/groups/{group_id}
# ---------------------------------------------------------------------------


def test_delete_group(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.flush()
        session.add(IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.ACTIVE_DETECTED))
        session.add(IPAddress(group_id=group.id, ip="10.0.0.2", status=IPStatus.ACTIVE_DETECTED))
        session.commit()
        group_id = str(group.id)

    resp = client.delete(f"/api/groups/{group_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Verify group and IPs are deleted
    with Session(db_engine) as session:
        assert session.get(Group, uuid.UUID(group_id)) is None
        ips = session.exec(select(IPAddress).where(IPAddress.group_id == uuid.UUID(group_id))).all()
        assert len(ips) == 0


def test_delete_group_not_found(client, auth_headers):
    fake_id = str(uuid.uuid4())
    resp = client.delete(f"/api/groups/{fake_id}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/ips/{ip_address}/reserve
# ---------------------------------------------------------------------------


def test_reserve_ip(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.flush()
        ip = IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.AVAILABLE_CANDIDATE)
        session.add(ip)
        session.commit()

    resp = client.put(
        "/api/ips/10.0.0.1/reserve",
        json={"status": "ASSIGNED_RESERVED"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ASSIGNED_RESERVED"
    assert "10.0.0.1" in data["message"]


def test_release_ip(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.flush()
        ip = IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.ASSIGNED_RESERVED)
        session.add(ip)
        session.commit()

    resp = client.put(
        "/api/ips/10.0.0.1/reserve",
        json={"status": "AVAILABLE_CANDIDATE"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "AVAILABLE_CANDIDATE"


def test_reserve_ip_not_found(client, auth_headers):
    resp = client.put(
        "/api/ips/10.0.0.99/reserve",
        json={"status": "ASSIGNED_RESERVED"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_reserve_ip_invalid_status(client, auth_headers):
    resp = client.put(
        "/api/ips/10.0.0.1/reserve",
        json={"status": "INVALID_STATUS"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/import
# ---------------------------------------------------------------------------


def test_import_csv(db_engine, client, auth_headers):
    csv_content = b"ip,hostname,group\n10.0.0.1,web-01,infra\n10.0.0.2,db-01,database\n"
    resp = client.post(
        "/api/import",
        files={"file": ("ips.csv", io.BytesIO(csv_content), "text/csv")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 2
    assert data["skipped"] == 0


def test_import_csv_with_group_override(db_engine, client, auth_headers):
    csv_content = b"ip,hostname\n10.0.0.1,web-01\n10.0.0.2,db-01\n"
    resp = client.post(
        "/api/import?group=override-group",
        files={"file": ("ips.csv", io.BytesIO(csv_content), "text/csv")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 2

    # Verify group override worked
    with Session(db_engine) as session:
        group = session.exec(select(Group).where(Group.name == "override-group")).first()
        assert group is not None
        ips = session.exec(select(IPAddress).where(IPAddress.group_id == group.id)).all()
        assert len(ips) == 2


def test_import_invalid_file_type(client, auth_headers):
    resp = client.post(
        "/api/import",
        files={"file": ("ips.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_import_invalid_ip_in_csv(db_engine, client, auth_headers):
    csv_content = b"ip,hostname\n10.0.0.1,web-01\nnot-an-ip,bad\n"
    resp = client.post(
        "/api/import",
        files={"file": ("ips.csv", io.BytesIO(csv_content), "text/csv")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 1
    assert data["skipped"] == 1
    assert len(data["errors"]) > 0


def test_import_duplicate_ip_skipped(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="default")
        session.add(group)
        session.flush()
        session.add(IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.ACTIVE_DETECTED))
        session.commit()

    csv_content = b"ip,hostname\n10.0.0.1,web-01\n10.0.0.2,web-02\n"
    resp = client.post(
        "/api/import",
        files={"file": ("ips.csv", io.BytesIO(csv_content), "text/csv")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 1
    assert data["skipped"] == 1
