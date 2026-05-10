"""Security package — credential encryption vault."""

from app.security.crypto import CredentialVault, generate_key

__all__ = ["CredentialVault", "generate_key"]
