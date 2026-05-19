"""HTTP Host header allow-list enforcement."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import DEFAULT_ALLOWED_HOSTS, Settings
from app.main import app


def _trusted_host_test_client(allowed_hosts: list[str]) -> TestClient:
    test_app = FastAPI()
    test_app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @test_app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(test_app)


def test_default_allowed_hosts_accepts_testclient_host() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_default_allowed_hosts_rejects_untrusted_host_header() -> None:
    client = _trusted_host_test_client(DEFAULT_ALLOWED_HOSTS)

    response = client.get("/api/health", headers={"host": "evil.example"})

    assert response.status_code == 400
    assert "Invalid host header" in response.text


def test_default_allowed_hosts_accepts_localhost_with_port() -> None:
    client = _trusted_host_test_client(DEFAULT_ALLOWED_HOSTS)

    response = client.get("/api/health", headers={"host": "localhost:8000"})

    assert response.status_code == 200


def test_allowed_hosts_setting_accepts_csv_and_wildcard() -> None:
    explicit = Settings(allowed_hosts="nms.example.com,localhost")
    wildcard = Settings(allowed_hosts="*")

    assert explicit.allowed_hosts == ["nms.example.com", "localhost"]
    assert wildcard.allowed_hosts == ["*"]
