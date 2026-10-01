#!/bin/bash
# run_webhook.sh — keeps webhook alive
# Usage: bash run_webhook.sh

set -e
cd "$(dirname "$0")"

echo "🚀 Starting Inbox Digest WhatsApp Webhook on port 8081..."
echo ""

# Load env
export $(grep -v '^#' .env | xargs)

# Run uvicorn via uv
exec uv run uvicorn whatsapp_webhook:app \
    --host 0.0.0.0 \
    --port 8081 \
    --log-level info \
    --no-access-log
