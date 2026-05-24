#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="$(cd "$(dirname "$0")/.." && pwd)/certs"
mkdir -p "$CERT_DIR"

if [[ -f "$CERT_DIR/server.key" && -f "$CERT_DIR/server.crt" ]]; then
  echo "certs already exist at $CERT_DIR (skip regeneration; delete files to refresh)"
  exit 0
fi

openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.crt" \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:app,IP:127.0.0.1"

chmod 600 "$CERT_DIR/server.key"
echo "Generated self-signed dev certs in $CERT_DIR (DO NOT commit)."
