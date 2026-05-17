"""Shared pytest configuration for backend tests."""

from __future__ import annotations

import os

# Keep API smoke tests isolated from Docker-only service names in .env.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("HTTPS_ENABLED", "false")
os.environ.setdefault("HTTPS_REDIRECT_ENABLED", "false")
