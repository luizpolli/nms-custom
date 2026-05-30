"""Password hashing helpers for local application users."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

_ITERATIONS = 210_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        _ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iter_s, salt_b64, digest_b64 = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iter_s))
        return hmac.compare_digest(actual, expected)
    except Exception as exc:  # noqa: BLE001 -- intentional: never leak password material
        # Logged at debug to keep the surface noiseless under traffic but
        # still let operators see corrupted hash payloads when debugging.
        # The encoded value is not logged; only the exception type.
        from loguru import logger

        logger.debug("verify_password: malformed encoded value ({})", type(exc).__name__)
        return False
