"""Shared pytest configuration for backend tests."""

from __future__ import annotations

import os

# Keep API smoke tests isolated from Docker/Compose runtime settings.
# Compose injects APP_ENV=development into the test container; tests must win.
os.environ["APP_ENV"] = "test"
os.environ["HTTPS_ENABLED"] = "false"
os.environ["HTTPS_REDIRECT_ENABLED"] = "false"
os.environ["EVENT_BUS_ENABLED"] = "false"
