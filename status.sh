#!/bin/sh
# ForexAI - stack status (macOS / Linux).
set -eu
cd "$(dirname "$0")"
echo ""
echo "============================================"
echo "  ForexAI - stack status"
echo "============================================"
echo ""
docker compose ps
echo ""
echo "Health endpoints:"
dash=$(grep -E "^DASHBOARD_PORT=" .env 2>/dev/null | cut -d= -f2); dash=${dash:-80}
api=$(grep -E "^API_PORT=" .env 2>/dev/null | cut -d= -f2); api=${api:-8080}
ai=$(grep -E "^AI_PORT=" .env 2>/dev/null | cut -d= -f2); ai=${ai:-8001}
for u in "dashboard http://localhost:${dash}/health" "API http://127.0.0.1:${api}/health" "API-ready http://127.0.0.1:${api}/health/ready" "AI http://127.0.0.1:${ai}/health" "AI-ready http://127.0.0.1:${ai}/ready"; do
  name=${u%% *}; url=${u#* }
  if curl -fsS -m 5 "$url" >/dev/null 2>&1; then echo "  [OK]   $name $url"; else echo "  [FAIL] $name $url"; fi
done
echo ""
echo "Stopped containers (forexai-db-migrate Exited 0 is NORMAL):"
docker compose ps -a --filter "status=exited"
