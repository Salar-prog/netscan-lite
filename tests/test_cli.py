"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner
from sqlmodel import Session

from netscan_lite.cli import cli
from netscan_lite.models import Group, IPAddress, IPStatus


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "ns-lite" in result.output


def test_groups_empty(runner):
    result = runner.invoke(cli, ["groups"])
    assert result.exit_code == 0
    assert "No groups found" in result.output


def test_groups_with_data(runner, cli_session: Session):
    group = Group(name="infra", miss_threshold=5, quarantine_hours=24)
    cli_session.add(group)
    cli_session.commit()

    result = runner.invoke(cli, ["groups"])
    assert result.exit_code == 0
    assert "infra" in result.output
    assert "miss_threshold=5" in result.output


def test_groups_json_output(runner, cli_session: Session):
    group = Group(name="infra")
    cli_session.add(group)
    cli_session.commit()

    result = runner.invoke(cli, ["groups", "--json-output"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["name"] == "infra"


def test_status_ip_found(runner, cli_session: Session):
    group = Group(name="infra")
    cli_session.add(group)
    cli_session.flush()
    ip = IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.ACTIVE_DETECTED, hostname="web-01")
    cli_session.add(ip)
    cli_session.commit()

    result = runner.invoke(cli, ["status", "10.0.0.1"])
    assert result.exit_code == 0
    assert "ACTIVE_DETECTED" in result.output
    assert "web-01" in result.output


def test_status_ip_not_found(runner):
    result = runner.invoke(cli, ["status", "10.0.0.99"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_available_empty(runner):
    result = runner.invoke(cli, ["available"])
    assert result.exit_code == 0
    assert "No available IPs found" in result.output


def test_available_with_data(runner, cli_session: Session):
    group = Group(name="infra")
    cli_session.add(group)
    cli_session.flush()
    ip = IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.AVAILABLE_CANDIDATE)
    cli_session.add(ip)
    cli_session.commit()

    result = runner.invoke(cli, ["available", "--count", "3"])
    assert result.exit_code == 0
    assert "10.0.0.1" in result.output


def test_available_json_output(runner, cli_session: Session):
    group = Group(name="infra")
    cli_session.add(group)
    cli_session.flush()
    ip = IPAddress(group_id=group.id, ip="10.0.0.1", status=IPStatus.AVAILABLE_CANDIDATE)
    cli_session.add(ip)
    cli_session.commit()

    result = runner.invoke(cli, ["available", "--json-output"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert data["available_ips"] == ["10.0.0.1"]


def test_import_csv(runner, tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("ip,hostname,group\n10.0.0.1,host1,infra\n10.0.0.2,,general\n")

    result = runner.invoke(cli, ["import-cmd", str(csv_file)])
    assert result.exit_code == 0
    assert "Imported: 2" in result.output


def test_import_file_not_found(runner):
    result = runner.invoke(cli, ["import-cmd", "/nonexistent/file.csv"])
    assert result.exit_code != 0
