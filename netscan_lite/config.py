import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Minimal configuration for ns-lite."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "sqlite:///./ns-lite.db"

    # Debug mode
    DEBUG: bool = False

    # Scanner defaults
    DEFAULT_MISS_THRESHOLD: int = 3
    DEFAULT_QUARANTINE_HOURS: int = 48
    NMAP_TIMEOUT_SECONDS: int = 300
    NMAP_TIMING_TEMPLATE: str = "-T4"
    TOP_TCP_PORTS: str = "80,443,22,445,3389,8080,8443,53"

    # LDAP authentication
    LDAP_ENABLED: bool = False
    LDAP_SERVER: str = "ldap://localhost"
    LDAP_BIND_DN: str = "cn=admin,dc=example,dc=com"
    LDAP_BIND_PASSWORD: str = ""
    LDAP_SEARCH_BASE: str = "dc=example,dc=com"
    LDAP_SEARCH_FILTER: str = "(sAMAccountName={username})"
    LDAP_STARTTLS: bool = False

    # JWT
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)
    JWT_EXPIRY_HOURS: int = 24


settings = Settings()
