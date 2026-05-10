"""Application settings loaded from environment / .env file."""

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Any


class Settings(BaseSettings):
    """Centralized settings for the NMS Custom application."""

    # Environment
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-me-to-a-real-secret-key"

    # Credential encryption
    credential_encryption_key: str = ""
    credential_encryption_iv: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://nms:nms_secret@postgres:5432/nms"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # SNMP
    snmp_default_community: str = "public"
    snmp_version: str = "v2c"

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Discovery
    discovery_chunk_size: int = 256
    discovery_poll_interval: int = 60
    discovery_timeout: int = 5

    # Polling
    poll_interval: int = 60
    poll_timeout: int = 10
    poll_workers: int = 4

    # Alarms
    alarm_poll_interval: int = 30
    alarm_workers: int = 2

    # Topology
    topology_poll_interval: int = 300

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": False}

    def model_post_init(self, _context: Any) -> None:
        """Parse CORS origins if provided as JSON string."""
        if isinstance(self.cors_origins, str):
            import ast

            try:
                self.cors_origins = ast.literal_eval(self.cors_origins)
            except (ValueError, SyntaxError):
                self.cors_origins = [self.cors_origins]


settings = Settings()

