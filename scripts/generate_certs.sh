#!/usr/bin/env sh
set -e

# Generates a self-signed certificate + key into ./nginx/certs
# Usage: ./scripts/generate_certs.sh

CERT_DIR="$(dirname "$0")/../nginx/certs"
mkdir -p "$CERT_DIR"

COMMON_NAME="45.10.41.250"

echo "Generating self-signed certificate for CN=$COMMON_NAME"

openssl req -x509 -nodes -days 3650 \
  -newkey rsa:2048 \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.crt" \
  -subj "/CN=$COMMON_NAME" \
  -addext "subjectAltName = IP:$COMMON_NAME, DNS:localhost"

chmod 644 "$CERT_DIR/server.crt"
chmod 600 "$CERT_DIR/server.key"

echo "Certificates written to $CERT_DIR"
