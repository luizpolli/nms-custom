"""Tests for the StarOS disc-reason code -> name lookup."""

from __future__ import annotations

from app.services.bulkstats.disc_reasons import disc_reason_code, disc_reason_name


def test_disc_reason_code_matches_field_name():
    assert disc_reason_code("disc-reason-1") == "1"
    assert disc_reason_code("disc-reason-633") == "633"


def test_disc_reason_code_rejects_non_matching_fields():
    assert disc_reason_code("disc-reason-summary") is None
    assert disc_reason_code("gtpu-curr-sess") is None


def test_disc_reason_name_known_codes():
    assert disc_reason_name("0") == "Unknown"
    assert disc_reason_name("1") == "Admin-disconnect"


def test_disc_reason_name_falls_back_for_unknown_code():
    assert disc_reason_name("999999") == "reason-999999"


def test_disc_reason_name_covers_full_published_range():
    # Sanity check that the bundled dictionary loaded the full StarOS
    # 21.26 disc-reason-0..633 range, not a truncated/empty file.
    assert disc_reason_name("632") == "gtpu-path-failure-s11u"
    assert disc_reason_name("633") == "gtpu-err-ind-s11u"
