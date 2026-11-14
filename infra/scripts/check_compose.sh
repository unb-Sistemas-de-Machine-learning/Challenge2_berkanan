#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

echo "=== Validando sintaxe e interpolação do compose.yaml ==="
docker compose config -q
echo "[OK] compose.yaml válido."
