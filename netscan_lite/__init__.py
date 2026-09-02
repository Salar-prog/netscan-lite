"""ns-lite: Lightweight IP discovery with quarantine logic."""

try:
    from importlib.metadata import version

    __version__ = version("netscan-lite")
except Exception:
    __version__ = "0.2.0"
