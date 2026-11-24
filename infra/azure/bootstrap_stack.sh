#!/usr/bin/env bash
# ==============================================================================
# Bootstrap idempotente da stack Challenge 2 Berkanan na VM Azure (brazilsouth)
# - Valida .env.prod (rejeita senhas padrão/placeholders)
# - Sobe PostgreSQL + ChromaDB
# - Executa migrações SQL idempotentes (migrations/migrate.sh) com SEED=0
# - Verifica/indexa coleção ChromaDB (scripts/ingest_chroma.py) quando vazia ou FORCE_REINDEX=1
# - Constrói e sobe backend + caddy (HTTPS automático) e valida /health
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/compose.prod.yaml"
ENV_FILE="${ENV_FILE:-${SCRIPT_DIR}/.env.prod}"
FORCE_REINDEX="${FORCE_REINDEX:-0}"
NETWORK_NAME="challenge2-berkanan-prod_berkanan_internal"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[ERRO] Arquivo de ambiente não encontrado: ${ENV_FILE}" >&2
  echo "       Copie infra/azure/.env.prod.example para infra/azure/.env.prod e preencha os segredos." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

if [[ -z "${API_DOMAIN:-}" ]]; then
  echo "[ERRO] API_DOMAIN não pode estar vazio em ${ENV_FILE}." >&2
  exit 1
fi

if [[ -z "${POSTGRES_PASSWORD:-}" || "${POSTGRES_PASSWORD}" == *"CHANGE_ME"* || "${POSTGRES_PASSWORD}" == "dev_only_change_me" ]]; then
  echo "[ERRO] Defina um POSTGRES_PASSWORD forte e exclusivo em ${ENV_FILE}." >&2
  exit 1
fi

COMPOSE=(docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}")

echo "=== 1. Validando compose.prod.yaml ==="
"${COMPOSE[@]}" config -q

echo "=== 2. Subindo PostgreSQL e ChromaDB ==="
"${COMPOSE[@]}" up -d --wait postgres chromadb

echo "=== 3. Executando migrações SQL idempotentes (SEED=0) ==="
docker run --rm \
  --network "${NETWORK_NAME}" \
  -e DB_HOST=postgres \
  -e DB_PORT=5432 \
  -e DB_NAME="${POSTGRES_DB:-berkanan_prod}" \
  -e DB_USER="${POSTGRES_USER:-berkanan_user}" \
  -e PGPASSWORD="${POSTGRES_PASSWORD}" \
  -e SEED=0 \
  -v "${REPO_ROOT}/migrations:/work/migrations:ro" \
  -v "${REPO_ROOT}/seeds:/work/seeds:ro" \
  postgres:16.4-bookworm \
  bash /work/migrations/migrate.sh

echo "=== 4. Construindo imagem do backend ==="
"${COMPOSE[@]}" build backend

echo "=== 5. Verificando coleção ChromaDB (${CHROMA_COLLECTION:-base_conhecimento_v2}) ==="
COLLECTION_NAME="${CHROMA_COLLECTION:-base_conhecimento_v2}"
MODEL_CACHE_VOL="challenge2-berkanan-prod_model_cache"
docker volume create "${MODEL_CACHE_VOL}" >/dev/null

CHROMA_COUNT="$(
  docker run --rm \
    --network "${NETWORK_NAME}" \
    -e CHROMA_HOST=chromadb \
    -e CHROMA_PORT=8000 \
    -e CHROMA_COLLECTION="${COLLECTION_NAME}" \
    -v "${MODEL_CACHE_VOL}:/home/appuser/.cache" \
    berkanan/challenge2-backend:prod \
    python3 -c '
import os, chromadb
client = chromadb.HttpClient(host=os.environ["CHROMA_HOST"], port=int(os.environ["CHROMA_PORT"]))
try:
    col = client.get_collection(name=os.environ["CHROMA_COLLECTION"])
    print(col.count())
except Exception:
    print(0)
'
)"

if [[ "${FORCE_REINDEX}" == "1" || "${CHROMA_COUNT}" -eq 0 ]]; then
  RECREATE_FLAG=""
  if [[ "${FORCE_REINDEX}" == "1" ]]; then
    RECREATE_FLAG="--recreate"
  fi
  echo "[INFO] Executando ingestão no ChromaDB (chunks atuais=${CHROMA_COUNT}, force=${FORCE_REINDEX})..."
  docker run --rm \
    --network "${NETWORK_NAME}" \
    --workdir /workspace \
    -e CHROMA_HOST=chromadb \
    -e CHROMA_PORT=8000 \
    -e CHROMA_COLLECTION="${COLLECTION_NAME}" \
    -e EMBEDDING_MODEL="${EMBEDDING_MODEL:-sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2}" \
    -e POSTGRES_HOST=postgres \
    -e POSTGRES_PORT=5432 \
    -e POSTGRES_DB="${POSTGRES_DB:-berkanan_prod}" \
    -e POSTGRES_USER="${POSTGRES_USER:-berkanan_user}" \
    -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
    -v "${MODEL_CACHE_VOL}:/home/appuser/.cache" \
    -v "${REPO_ROOT}/data:/workspace/data:ro" \
    -v "${REPO_ROOT}/scripts:/workspace/scripts:ro" \
    berkanan/challenge2-backend:prod \
    python3 /workspace/scripts/ingest_chroma.py --host chromadb --port 8000 --collection "${COLLECTION_NAME}" ${RECREATE_FLAG}
else
  echo "[OK] Coleção '${COLLECTION_NAME}' já possui ${CHROMA_COUNT} trechos indexados."
fi

echo "=== 6. Subindo backend e proxy TLS (Caddy) ==="
"${COMPOSE[@]}" up -d --wait --remove-orphans backend caddy

echo "=== 7. Validando saúde interna do backend (/health) ==="
"${COMPOSE[@]}" exec -T backend python3 -c '
import json, sys, urllib.request
with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5) as resp:
    data = json.loads(resp.read().decode("utf-8"))
print(json.dumps(data, ensure_ascii=False))
if data.get("status") != "healthy":
    sys.exit(1)
'

echo "[SUCESSO] Stack Azure operacional em https://${API_DOMAIN}"
