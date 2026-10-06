#!/bin/sh
# ForexAI - recent logs (macOS / Linux).
set -eu
cd "$(dirname "$0")"
docker compose logs --tail 100
docker compose logs --tail 200 > logs.txt 2>&1
echo "Full output saved to logs.txt"
