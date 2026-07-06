#!/bin/bash
# Generate self-signed TLS certificates for local development.
# Production: replace with Let's Encrypt via Certbot.

set -e

CERTS_DIR="$(cd "$(dirname "$0")/../certs" && pwd)"
mkdir -p "$CERTS_DIR"

if [ -f "$CERTS_DIR/server.crt" ] && [ -f "$CERTS_DIR/server.key" ]; then
    echo "Certificates already exist at $CERTS_DIR"
    echo "  $CERTS_DIR/server.crt"
    echo "  $CERTS_DIR/server.key"
    echo "Delete them to regenerate."
    exit 0
fi

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$CERTS_DIR/server.key" \
    -out "$CERTS_DIR/server.crt" \
    -subj "/C=RO/ST=Bucharest/L=Bucharest/O=Operion/CN=localhost"

echo "Self-signed certificates generated:"
echo "  $CERTS_DIR/server.crt"
echo "  $CERTS_DIR/server.key"
