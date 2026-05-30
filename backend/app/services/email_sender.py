"""Thin SMTP wrapper that is a no-op when SMTP_HOST is unset.

Reads SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD,
SMTP_FROM (default SMTP_USER) from environment variables.
All parameters are optional — if SMTP_HOST is missing the function logs
a warning and returns without raising.
"""

from __future__ import annotations

import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger


def send_email(
    *,
    recipients: list[str],
    subject: str,
    body: str,
    attachment_bytes: bytes | None = None,
    attachment_filename: str | None = None,
    attachment_mimetype: str = "application/octet-stream",
) -> bool:
    """Send a plain-text email with an optional attachment.

    Returns True when sent, False when SMTP is not configured (no-op).
    Raises on SMTP errors.
    """
    host = os.environ.get("SMTP_HOST", "")
    if not host:
        logger.warning("SMTP_HOST not set — skipping email delivery to {}", recipients)
        return False

    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("SMTP_FROM", user)

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    if attachment_bytes and attachment_filename:
        part = MIMEBase(*attachment_mimetype.split("/", 1))
        part.set_payload(attachment_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{attachment_filename}"')
        msg.attach(part)

    with smtplib.SMTP(host, port) as server:
        server.ehlo()
        if port != 25:
            server.starttls()
        if user and password:
            server.login(user, password)
        server.sendmail(from_addr, recipients, msg.as_string())

    logger.info("Email sent to {} subject={!r}", recipients, subject)
    return True
