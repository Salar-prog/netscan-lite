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


settings = Settings()
