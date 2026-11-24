#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

echo "=== Validando sintaxe e interpolação do compose.yaml (dev) ==="
docker compose config -q
echo "[OK] compose.yaml válido."

echo "=== Validando sintaxe e interpolação de infra/azure/compose.prod.yaml ==="
docker compose \
  -f infra/azure/compose.prod.yaml \
  --env-file infra/azure/.env.prod.example \
  config -q
echo "[OK] infra/azure/compose.prod.yaml válido."
