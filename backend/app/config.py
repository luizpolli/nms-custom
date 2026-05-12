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

    # API authentication (enable in deployed environments)
    api_auth_enabled: bool = False
    api_keys: str | list[str] = ""
    root_web_login_enabled: bool = False
    max_parallel_sessions: int = 5
    idle_timeout_minutes: int = 30

    # HTTPS / TLS
    https_enabled: bool = False
    https_redirect_enabled: bool = True
    tls_min_version: str = "TLSv1.3"
    tls_cert_file: str = ""
    tls_key_file: str = ""
    tls_ca_file: str = ""
    require_signed_html_certificate: bool = True

    # Discovery
    discovery_chunk_size: int = 256
    discovery_max_hosts: int = 4096
    discovery_poll_interval: int = 60
    discovery_timeout: int = 5

    # Upload limits
    mib_upload_max_bytes: int = 5 * 1024 * 1024
    mib_allowed_extensions: list[str] = Field(default_factory=lambda: [".mib", ".my", ".txt"])

    # SSH security
    ssh_known_hosts_path: str = ""
    ssh_disable_host_key_checking: bool = False

    # Cisco lifecycle APIs (optional; falls back to local registry when unset)
    cisco_api_token: str = ""
    cisco_eox_base_url: str = "https://apix.cisco.com/supporttools/eox/rest/5"

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
        if isinstance(self.mib_allowed_extensions, str):
            self.mib_allowed_extensions = [x.strip().lower() for x in self.mib_allowed_extensions.split(",") if x.strip()]


settings = Settings()
