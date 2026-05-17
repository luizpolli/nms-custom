"""Application settings loaded from environment / .env file."""

from pydantic import Field, model_validator
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
    postgres_user: str = "nms"
    postgres_password: str = "nms_secret"
    postgres_db: str = "nms"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # Redis
    redis_url: str = "redis://redis:6379/0"
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # Event bus
    event_bus_enabled: bool = True
    event_stream_name: str = "nms:events"

    # SNMP
    snmp_default_community: str = "public"
    snmp_version: str = "v2c"

    # CORS / hosts
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    allowed_hosts: str | list[str] = "*"

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
    backend_port: int = 8000
    frontend_port: int = 5173

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
    monitoring_policy_check_interval: int = 30
    report_schedule_check_interval: int = 60
    start_embedded_workers: bool = True

    # Syslog
    syslog_enabled: bool = True
    # Container syslog receiver; port exposure is controlled by Compose/K8s/firewall.
    syslog_bind_host: str = "0.0.0.0"  # nosec B104
    syslog_bind_port: int = 5514

    # Alarms
    alarm_poll_interval: int = 30
    alarm_workers: int = 2

    # Topology
    topology_poll_interval: int = 300
    lldp_interval: int = 120
    cdp_interval: int = 120

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def build_connection_urls(self) -> "Settings":
        """Build canonical connection URLs from compose-style env vars when URLs are unset."""
        default_db = "postgresql+asyncpg://nms:nms_secret@postgres:5432/nms"
        if self.database_url == default_db:
            self.database_url = (
                f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )

        default_redis = "redis://redis:6379/0"
        if self.redis_url == default_redis:
            auth = f":{self.redis_password}@" if self.redis_password else ""
            self.redis_url = f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return self

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
