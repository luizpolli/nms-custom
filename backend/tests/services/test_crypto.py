"""Tests for CredentialVault AES-256-GCM encryption."""

from __future__ import annotations

import base64
import os

import pytest

from app.security.crypto import CredentialVault, generate_key


def _new_vault() -> CredentialVault:
    key_b64, iv_b64 = generate_key()
    return CredentialVault(key_b64, iv_b64)


def test_round_trip_encrypt_decrypt() -> None:
    vault = _new_vault()
    record_id = b"test-record-001"
    plaintext = "super-secret-password"

    ciphertext = vault.encrypt(plaintext, record_id)
    assert ciphertext != plaintext

    recovered = vault.decrypt(ciphertext, record_id)
    assert recovered == plaintext


def test_different_record_id_produces_different_ciphertext() -> None:
    vault = _new_vault()
    plaintext = "same-secret"
    ct1 = vault.encrypt(plaintext, b"record-aaa")
    ct2 = vault.encrypt(plaintext, b"record-bbb")
    assert ct1 != ct2


def test_wrong_key_fails_decrypt() -> None:
    vault_a = _new_vault()
    vault_b = _new_vault()
    record_id = b"some-record"

    ciphertext = vault_a.encrypt("confidential", record_id)

    with pytest.raises(ValueError, match="Decryption failed"):
        vault_b.decrypt(ciphertext, record_id)


def test_invalid_key_length_raises() -> None:
    short_key = base64.b64encode(os.urandom(16)).decode()
    with pytest.raises(ValueError):
        CredentialVault(short_key)


def test_invalid_base64_raises() -> None:
    with pytest.raises(ValueError):
        CredentialVault("not-valid-base64!!!")
