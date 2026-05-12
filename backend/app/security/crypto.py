"""AES-256-GCM credential vault with random per-encryption nonces.

Usage:
    vault = CredentialVault.from_settings(settings)
    ciphertext = vault.encrypt("s3cr3t", record_id=b"uuid-bytes-here")
    plaintext  = vault.decrypt(ciphertext, record_id=b"uuid-bytes-here")
"""

from __future__ import annotations

import base64
import os
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from loguru import logger

if TYPE_CHECKING:
    from app.config import Settings

_NONCE_LEN = 12  # GCM standard nonce length


def generate_key() -> tuple[str, str]:
    """Generate a random AES-256 key and IV suitable for .env.

    Returns:
        (key_b64, iv_b64) — 32-byte key and 16-byte IV, both base64-encoded.
    """
    key = base64.b64encode(os.urandom(32)).decode()
    iv = base64.b64encode(os.urandom(16)).decode()
    return key, iv


class CredentialVault:
    """AES-256-GCM vault.  One instance per application lifetime."""

    __slots__ = ("_key_bytes", "_aesgcm")

    def __init__(self, key_b64: str, iv_b64: str = "") -> None:
        """Initialise the vault.

        Args:
            key_b64: Base64-encoded 32-byte AES key.
            iv_b64:  Accepted for backwards compatibility; unused for v2 ciphertexts.
        """
        try:
            self._key_bytes: bytes = base64.b64decode(key_b64)
        except Exception as exc:
            raise ValueError("credential_encryption_key is not valid base64") from exc
        if len(self._key_bytes) != 32:
            raise ValueError(
                f"credential_encryption_key must decode to 32 bytes, got {len(self._key_bytes)}"
            )
        self._aesgcm = AESGCM(self._key_bytes)
        logger.debug("CredentialVault initialised (AES-256-GCM)")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encrypt(self, plaintext: str, record_id: bytes) -> str:
        """Encrypt *plaintext* and return v2:base64(nonce+ciphertext+tag).

        Args:
            plaintext:  The secret string to encrypt.
            record_id:  Stable unique bytes for this record (e.g. UUID bytes).
        """
        nonce = os.urandom(_NONCE_LEN)
        ct = self._aesgcm.encrypt(nonce, plaintext.encode(), None)
        return "v2:" + base64.b64encode(nonce + ct).decode()

    def decrypt(self, ciphertext_b64: str, record_id: bytes) -> str:
        """Decrypt a base64-encoded ciphertext produced by :meth:`encrypt`.

        Args:
            ciphertext_b64: Value returned by :meth:`encrypt`.
            record_id:      Same bytes that were used during encryption.

        Raises:
            ValueError: If the tag is invalid or the key is wrong.
        """
        try:
            if ciphertext_b64.startswith("v2:"):
                raw = base64.b64decode(ciphertext_b64[3:])
                nonce, ct = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
                return self._aesgcm.decrypt(nonce, ct, None).decode()
            # Backwards compatibility for legacy deterministic-nonce ciphertexts.
            raw = base64.b64decode(ciphertext_b64)
            nonce = self._derive_legacy_nonce(record_id)
            return self._aesgcm.decrypt(nonce, raw, None).decode()
        except Exception as exc:
            raise ValueError("Decryption failed — wrong key or corrupted ciphertext") from exc

    def rotate(self, old_ciphertext_b64: str, record_id: bytes, old_vault: CredentialVault) -> str:
        """Re-encrypt *old_ciphertext_b64* from *old_vault* under the current key.

        Args:
            old_ciphertext_b64: Ciphertext encrypted by *old_vault*.
            record_id:          Record identifier bytes.
            old_vault:          Vault instance holding the previous key.
        """
        plaintext = old_vault.decrypt(old_ciphertext_b64, record_id)
        return self.encrypt(plaintext, record_id)

    # ------------------------------------------------------------------
    # Class-level helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls, settings: Settings) -> CredentialVault:
        """Build a vault from application settings.

        Raises:
            RuntimeError: If ``credential_encryption_key`` is empty.
        """
        if not settings.credential_encryption_key:
            raise RuntimeError(
                "credential_encryption_key is not set. "
                "Generate one with: python -c \"from app.security.crypto import generate_key; "
                "k,iv=generate_key(); print(f'CREDENTIAL_ENCRYPTION_KEY={k}\\nCREDENTIAL_ENCRYPTION_IV={iv}')\""
            )
        return cls(settings.credential_encryption_key, settings.credential_encryption_iv)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _derive_legacy_nonce(self, record_id: bytes) -> bytes:
        """Derive the legacy deterministic nonce for old ciphertext migration."""
        import hashlib
        import hmac

        digest = hmac.new(self._key_bytes, record_id, hashlib.sha256).digest()
        return digest[:_NONCE_LEN]
