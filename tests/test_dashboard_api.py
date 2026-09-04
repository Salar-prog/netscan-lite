"""Tests for dashboard API endpoints (stats, import, groups CRUD, reserve)."""

import io
import uuid

from sqlmodel import Session, select

from netscan_lite.models import Group, IPAddress, IPStatus

# ---------------------------------------------------------------------------
# GET /api/stats
# ---------------------------------------------------------------------------


def test_stats_empty(client, auth_headers):
    resp = client.get("/api/v1/stats", headers=auth_headers)
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

    resp = client.get("/api/v1/stats", headers=auth_headers)
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
    resp = client.get("/api/v1/groups-detail", headers=auth_headers)
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

    resp = client.get("/api/v1/groups-detail", headers=auth_headers)
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
        f"/api/v1/groups/{group_id}",
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
        f"/api/v1/groups/{fake_id}",
        json={"miss_threshold": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_update_group_invalid_id(client, auth_headers):
    resp = client.put(
        "/api/v1/groups/not-a-uuid",
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

    resp = client.delete(f"/api/v1/groups/{group_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Verify group and IPs are deleted
    with Session(db_engine) as session:
        assert session.get(Group, uuid.UUID(group_id)) is None
        ips = session.exec(select(IPAddress).where(IPAddress.group_id == uuid.UUID(group_id))).all()
        assert len(ips) == 0


def test_delete_group_not_found(client, auth_headers):
    fake_id = str(uuid.uuid4())
    resp = client.delete(f"/api/v1/groups/{fake_id}", headers=auth_headers)
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
        "/api/v1/ips/10.0.0.1/reserve",
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
        "/api/v1/ips/10.0.0.1/reserve",
        json={"status": "AVAILABLE_CANDIDATE"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "AVAILABLE_CANDIDATE"


def test_reserve_ip_not_found(client, auth_headers):
    resp = client.put(
        "/api/v1/ips/10.0.0.99/reserve",
        json={"status": "ASSIGNED_RESERVED"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_reserve_ip_invalid_status(client, auth_headers):
    resp = client.put(
        "/api/v1/ips/10.0.0.1/reserve",
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
        "/api/v1/import",
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
        "/api/v1/import?group=override-group",
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
        "/api/v1/import",
        files={"file": ("ips.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_import_invalid_ip_in_csv(db_engine, client, auth_headers):
    csv_content = b"ip,hostname\n10.0.0.1,web-01\nnot-an-ip,bad\n"
    resp = client.post(
        "/api/v1/import",
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
        "/api/v1/import",
        files={"file": ("ips.csv", io.BytesIO(csv_content), "text/csv")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 1
    assert data["skipped"] == 1


# ---------------------------------------------------------------------------
# GET /api/ips (paginated list)
# ---------------------------------------------------------------------------


def test_list_ips_empty(client, auth_headers):
    resp = client.get("/api/v1/ips", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ips"] == []
    assert data["total"] == 0
    assert data["page"] == 1


def test_list_ips_with_data(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.flush()
        session.add(IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.ACTIVE_DETECTED, hostname="web-01"))
        session.add(IPAddress(group_id=group.id, ip="10.0.0.2", status=IPStatus.AVAILABLE_CANDIDATE, hostname="db-01"))
        session.commit()

    resp = client.get("/api/v1/ips", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["ips"]) == 2
    ips = {i["ip"]: i for i in data["ips"]}
    assert ips["10.0.0.1"]["hostname"] == "web-01"
    assert ips["10.0.0.1"]["status"] == "ACTIVE_DETECTED"
    assert ips["10.0.0.1"]["group_name"] == "infra"


def test_list_ips_filter_by_status(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.flush()
        session.add(IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.ACTIVE_DETECTED))
        session.add(IPAddress(group_id=group.id, ip="10.0.0.2", status=IPStatus.AVAILABLE_CANDIDATE))
        session.commit()

    resp = client.get("/api/v1/ips?status=ACTIVE_DETECTED", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["ips"][0]["ip"] == "10.0.0.1"


def test_list_ips_filter_by_group(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        g1 = Group(name="infra")
        g2 = Group(name="db")
        session.add(g1)
        session.add(g2)
        session.flush()
        session.add(IPAddress(group_id=g1.id, ip="10.0.0.1", status=IPStatus.ACTIVE_DETECTED))
        session.add(IPAddress(group_id=g2.id, ip="10.0.0.2", status=IPStatus.ACTIVE_DETECTED))
        session.commit()

    resp = client.get("/api/v1/ips?group=infra", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["ips"][0]["ip"] == "10.0.0.1"


def test_list_ips_search(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.flush()
        session.add(IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.ACTIVE_DETECTED, hostname="web-01"))
        session.add(IPAddress(group_id=group.id, ip="10.0.0.2", status=IPStatus.ACTIVE_DETECTED, hostname="db-01"))
        session.commit()

    resp = client.get("/api/v1/ips?search=web", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["ips"][0]["hostname"] == "web-01"


def test_list_ips_search_underscore(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.flush()
        session.add(IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.ACTIVE_DETECTED, hostname="web_01"))
        session.add(IPAddress(group_id=group.id, ip="10.0.0.2", status=IPStatus.ACTIVE_DETECTED, hostname="db_01"))
        session.commit()

    resp = client.get("/api/v1/ips?search=web_01", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["ips"][0]["hostname"] == "web_01"


def test_list_ips_search_percent(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.flush()
        session.add(IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.ACTIVE_DETECTED, hostname="100%"))
        session.commit()

    resp = client.get("/api/v1/ips?search=100%25", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


def test_list_ips_pagination(db_engine, client, auth_headers):
    with Session(db_engine) as session:
        group = Group(name="infra")
        session.add(group)
        session.flush()
        for i in range(5):
            session.add(IPAddress(group_id=group.id, ip=f"10.0.0.{i + 1}", status=IPStatus.ACTIVE_DETECTED))
        session.commit()

    resp = client.get("/api/v1/ips?page=1&page_size=2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["ips"]) == 2
    assert data["page"] == 1

    resp2 = client.get("/api/v1/ips?page=3&page_size=2", headers=auth_headers)
    data2 = resp2.json()
    assert len(data2["ips"]) == 1


def test_list_ips_invalid_status(client, auth_headers):
    resp = client.get("/api/v1/ips?status=INVALID", headers=auth_headers)
    assert resp.status_code == 400


def test_list_ips_group_not_found(client, auth_headers):
    resp = client.get("/api/v1/ips?group=nonexistent", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/ips/{ip}/scan (scan single IP)
# ---------------------------------------------------------------------------


def test_scan_single_ip_not_found(client, auth_headers):
    resp = client.post("/api/v1/ips/10.0.0.99/scan", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# WS /ws/scan
# ---------------------------------------------------------------------------


def test_ws_scan_rejects_invalid_json(db_engine, client):
    """WebSocket with invalid JSON payload should return error and close."""
    with client.websocket_connect("/ws/scan?token=test-token") as ws:
        ws.send_text("not-json")
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "Invalid JSON" in data["detail"]


def test_ws_scan_missing_group_or_ips(db_engine, client):
    """WebSocket with empty payload should return error."""
    with client.websocket_connect("/ws/scan?token=test-token") as ws:
        ws.send_json({})
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "Provide either" in data["detail"]


def test_ws_scan_group_not_found(db_engine, client):
    """WebSocket with nonexistent group should return error."""
    with client.websocket_connect("/ws/scan?token=test-token") as ws:
        ws.send_json({"group": "nonexistent"})
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "not found" in data["detail"]


def test_ws_scan_invalid_ip(db_engine, client):
    """WebSocket with invalid IP should return error."""
    with client.websocket_connect("/ws/scan?token=test-token") as ws:
        ws.send_json({"ips": ["not-an-ip"]})
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "Invalid IPv4" in data["detail"]
