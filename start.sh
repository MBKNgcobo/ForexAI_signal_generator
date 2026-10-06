#!/bin/sh
# ForexAI - start the Docker stack (macOS / Linux).
# Mirrors scripts/start-forexai.bat. Requires Docker + Compose v2.
set -eu
cd "$(dirname "$0")"

echo ""
echo "============================================"
echo "  ForexAI - starting the Docker stack"
echo "============================================"
echo ""

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] Docker is not installed. Install Docker Desktop first:"
  echo "        https://docs.docker.com/get-docker/"
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "[ERROR] Docker is installed but not running."
  echo "        Start Docker Desktop, wait until it finishes, then retry."
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "[ERROR] Docker Compose v2 is not available. Update Docker Desktop."
  exit 1
fi

if [ ! -f ".env" ]; then
  if [ ! -f ".env.example" ]; then
    echo "[ERROR] Neither .env nor .env.example found. Incomplete package."
    exit 1
  fi
  cp ".env.example" ".env"
  echo "[SETUP] Created .env from .env.example."
  echo "        Edit .env (POSTGRES_PASSWORD, JWT_KEY, TWELVE_DATA_API_KEY,"
  echo "        OPENROUTER_API_KEY), save it, then run this script again."
  exit 1
fi

for v in POSTGRES_PASSWORD JWT_KEY TWELVE_DATA_API_KEY OPENROUTER_API_KEY; do
  if grep -q "^${v}=replace-me" .env 2>/dev/null; then
    echo "[ERROR] $v in .env is still a placeholder. Edit .env and retry."
    exit 1
  fi
done

echo "Building images and starting the stack (first run takes minutes)..."
docker compose up -d --build

echo "Waiting for services to become healthy..."
waited=0
while [ "$waited" -lt 180 ]; do
  sleep 2
  waited=$((waited + 2))
  ok=1
  for c in forexai-postgres forexai-python-ai forexai-csharp-api forexai-dashboard; do
    st=$(docker inspect -f "{{.State.Health.Status}}" "$c" 2>/dev/null || echo starting)
    [ "$st" = "healthy" ] || { ok=0; break; }
  done
  [ "$ok" = "1" ] && break
done

docker compose ps
port=$(grep -E "^DASHBOARD_PORT=" .env 2>/dev/null | cut -d= -f2)
echo ""
echo "  Open the dashboard at:  http://localhost:${port:-80}"
echo ""
