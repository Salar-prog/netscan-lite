import logging
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_SECRET_DIR = Path.home() / ".ns-lite"
_SECRET_FILE = _SECRET_DIR / "jwt-secret"


def _resolve_jwt_secret() -> str:
    """Resolve JWT secret: env var > file > generate and persist."""
    # Check if explicitly set via env (pydantic-settings handles this before we're called)
    if _SECRET_FILE.exists():
        try:
            return _SECRET_FILE.read_text().strip()
        except OSError:
            logger.warning("Could not read %s, generating new secret", _SECRET_FILE)

    # Generate and persist
    secret = secrets.token_urlsafe(32)
    try:
        _SECRET_DIR.mkdir(parents=True, exist_ok=True)
        _SECRET_FILE.write_text(secret)
        _SECRET_FILE.chmod(0o600)
        logger.info("Generated JWT secret, persisted to %s", _SECRET_FILE)
    except OSError:
        logger.warning("Could not persist JWT secret to %s — secret will change on restart", _SECRET_FILE)

    return secret


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
    DEV_AUTH_ENABLED: bool = False
    LDAP_SERVER: str = "ldap://localhost"
    LDAP_BIND_DN: str = "cn=admin,dc=example,dc=com"
    LDAP_BIND_PASSWORD: str = ""
    LDAP_SEARCH_BASE: str = "dc=example,dc=com"
    LDAP_SEARCH_FILTER: str = "(sAMAccountName={username})"
    LDAP_USE_SSL: bool = False

    # JWT
    JWT_SECRET_KEY: str = ""
    JWT_EXPIRY_HOURS: int = 24

    # API base URL (used by CLI auth command)
    API_BASE_URL: str = "http://127.0.0.1:8000"

    # CORS (empty = disabled; set to your domain in production, e.g. ["https://ns-lite.internal"])
    CORS_ORIGINS: list[str] = []

    # Authorization
    ADMIN_GROUPS: list[str] = ["ns-lite-admins"]

    # Monitoring
    ENABLE_METRICS: bool = False
    LOG_JSON: bool = False

    def model_post_init(self, __context: object) -> None:
        if not self.JWT_SECRET_KEY:
            object.__setattr__(self, "JWT_SECRET_KEY", _resolve_jwt_secret())

    def validate_production_config(self) -> list[str]:
        """Validate config for production use. Returns list of warnings."""
        warnings = []
        if self.LDAP_ENABLED and not self.LDAP_BIND_PASSWORD:
            warnings.append("LDAP_ENABLED=true but LDAP_BIND_PASSWORD is empty")
        if not self.LDAP_ENABLED and not self.DEV_AUTH_ENABLED and not self.DEBUG:
            warnings.append("Neither LDAP nor DEV_AUTH enabled — no authentication active")
        if self.LDAP_ENABLED and self.CORS_ORIGINS == ["*"]:
            warnings.append("CORS_ORIGINS is ['*'] in production — lock this down")
        return warnings


settings = Settings()
