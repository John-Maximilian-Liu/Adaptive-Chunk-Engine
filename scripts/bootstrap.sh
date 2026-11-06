#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
cp -n .env.example .env || true
if [[ "${FIX_DOCKER_BRIDGE:-1}" == "1" ]] && [[ -x "$ROOT/scripts/fix-docker-bridge-forwarding.sh" ]]; then
  "$ROOT/scripts/fix-docker-bridge-forwarding.sh" || true
fi
docker compose up -d --build
echo "API: http://localhost:8000/docs"
echo "Web: http://localhost:3000"
echo "Health: http://localhost:8000/api/v1/health/ready"
