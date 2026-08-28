"""Tests for nmap XML parsing in NmapScanner."""

import pytest

from netscan_lite.scanner.runner import NmapScanner


@pytest.fixture
def scanner():
    return NmapScanner()


SIMPLE_HOST_UP = """<?xml version="1.0" encoding="UTF-8"?>
<nmaprun>
  <host>
    <status state="up" reason="syn-ack"/>
    <address addrtype="ipv4" addr="10.0.0.1"/>
    <hostnames><hostname name="web-01" type="PTR"/></hostnames>
    <ports>
      <port protocol="tcp" portid="443">
        <state state="open" reason="syn-ack"/>
        <service name="https" product="nginx" version="1.24"/>
      </port>
      <port protocol="tcp" portid="80">
        <state state="open" reason="syn-ack"/>
        <service name="http" product="nginx"/>
      </port>
    </ports>
  </host>
</nmaprun>"""

HOST_DOWN = """<?xml version="1.0" encoding="UTF-8"?>
<nmaprun>
  <host>
    <status state="down" reason="no-response"/>
    <address addrtype="ipv4" addr="10.0.0.99"/>
  </host>
</nmaprun>"""

MULTI_HOST = """<?xml version="1.0" encoding="UTF-8"?>
<nmaprun>
  <host>
    <status state="up" reason="arp-response"/>
    <address addrtype="ipv4" addr="10.0.0.1"/>
    <address addrtype="mac" addr="AA:BB:CC:DD:EE:FF" vendor="Cisco"/>
    <hostnames><hostname name="router" type="PTR"/></hostnames>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open" reason="syn-ack"/>
        <service name="ssh" product="OpenSSH" version="9.3"/>
      </port>
    </ports>
  </host>
  <host>
    <status state="up" reason="echo-reply"/>
    <address addrtype="ipv4" addr="10.0.0.2"/>
    <ports>
      <port protocol="tcp" portid="8080">
        <state state="open|filtered" reason="no-response"/>
        <service name="http-proxy"/>
      </port>
    </ports>
  </host>
</nmaprun>"""


def test_parse_host_up_with_ports(scanner: NmapScanner):
    results = scanner.parse_nmap_xml(SIMPLE_HOST_UP)

    assert "10.0.0.1" in results
    host = results["10.0.0.1"]
    assert host.is_up is True
    assert host.hostname == "web-01"
    assert len(host.open_ports) == 2
    assert host.open_ports[0].port == 443
    assert host.open_ports[0].service == "https"
    assert host.open_ports[0].product == "nginx"
    assert host.open_ports[0].version == "1.24"


def test_parse_host_down(scanner: NmapScanner):
    results = scanner.parse_nmap_xml(HOST_DOWN)

    assert "10.0.0.99" in results
    host = results["10.0.0.99"]
    assert host.is_up is False
    assert host.status_reason == "no-response"
    assert host.open_ports == []


def test_parse_multiple_hosts(scanner: NmapScanner):
    results = scanner.parse_nmap_xml(MULTI_HOST)

    assert len(results) == 2

    router = results["10.0.0.1"]
    assert router.is_up is True
    assert router.hostname == "router"
    assert router.mac_address == "AA:BB:CC:DD:EE:FF"
    assert router.mac_vendor == "Cisco"
    assert router.open_ports[0].port == 22
    assert router.open_ports[0].product == "OpenSSH"

    web = results["10.0.0.2"]
    assert web.is_up is True
    assert web.mac_address is None


def test_parse_empty_xml(scanner: NmapScanner):
    results = scanner.parse_nmap_xml("")
    assert results == {}


def test_parse_malformed_xml(scanner: NmapScanner):
    with pytest.raises(ValueError, match="Failed to parse"):
        scanner.parse_nmap_xml("not xml at all")


def test_discovery_method_mapping(scanner: NmapScanner):
    assert scanner._map_reason_to_method("arp-response", True) == "ARP"
    assert scanner._map_reason_to_method("echo-reply", False) == "ICMP"
    assert scanner._map_reason_to_method("syn-ack", False) == "TCP_SYN"
    assert scanner._map_reason_to_method("conn-refused", False) == "TCP_CONNECT"
    assert scanner._map_reason_to_method("unknown", False) == "TCP_CONNECT"


def test_closed_ports_not_included(scanner: NmapScanner):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<nmaprun>
  <host>
    <status state="up" reason="syn-ack"/>
    <address addrtype="ipv4" addr="10.0.0.1"/>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="closed" reason="reset"/>
      </port>
      <port protocol="tcp" portid="443">
        <state state="open" reason="syn-ack"/>
        <service name="https"/>
      </port>
    </ports>
  </host>
</nmaprun>"""

    results = scanner.parse_nmap_xml(xml)
    host = results["10.0.0.1"]
    assert len(host.open_ports) == 1
    assert host.open_ports[0].port == 443
