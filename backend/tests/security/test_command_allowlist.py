"""Tests for command allow-list enforcement."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config import settings
from app.security import allowlist
from app.security.allowlist import assert_command_allowed


def test_empty_command_allowlist_allows_dev_commands(monkeypatch):
    monkeypatch.setattr(settings, "command_allowlist", "")
    allowlist._compiled_patterns.cache_clear()

    assert_command_allowed("show version")


def test_command_allowlist_permits_matching_pattern(monkeypatch):
    monkeypatch.setattr(settings, "command_allowlist", r"show\s+.*")
    allowlist._compiled_patterns.cache_clear()

    assert_command_allowed("show ip interface brief")


def test_command_allowlist_rejects_non_matching_pattern(monkeypatch):
    monkeypatch.setattr(settings, "command_allowlist", r"show\s+.*")
    allowlist._compiled_patterns.cache_clear()

    with pytest.raises(HTTPException) as exc:
        assert_command_allowed("configure terminal")

    assert exc.value.status_code == 422
