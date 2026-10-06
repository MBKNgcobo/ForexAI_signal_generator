#!/bin/sh
# ForexAI - stop the Docker stack (macOS / Linux). Data is kept.
set -eu
cd "$(dirname "$0")"
echo "Stopping the ForexAI stack. All data is kept."
docker compose down
echo "[OK] Stack stopped. Restart with ./start.sh"
