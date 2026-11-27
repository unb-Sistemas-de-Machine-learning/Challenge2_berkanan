#!/usr/bin/env bash
# ==============================================================================
# Exportação LGPD-safe de métricas SQL da VM Azure (Challenge 2 Berkanan)
# - Exporta views agregadas (vw_metricas_agregadas_diarias e
#   vw_checagem_limiares_monitoramento) em CSV
# - Exporta pg_dump somente da tabela metricas_requisicao (sem PII/fotos)
# - Gera export_metadata.txt sem segredos, sem PII e sem imagens
# - Executa localmente via docker compose exec -T postgres (sem expor porta 5432)
# ==============================================================================

set -euo pipefail

OUTPUT_DIR="${1:-/tmp/berkanan-metrics-export}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/compose.prod.yaml"
ENV_FILE="${ENV_FILE:-${SCRIPT_DIR}/.env.prod}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[ERRO] Arquivo de ambiente não encontrado: ${ENV_FILE}" >&2
  echo "       Verifique se a stack Azure foi inicializada antes da exportação." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

DB_USER="${POSTGRES_USER:-berkanan_user}"
DB_NAME="${POSTGRES_DB:-berkanan_prod}"
COMPOSE=(docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}")

exec_postgres() {
  PGPASSWORD="${POSTGRES_PASSWORD:-}" "${COMPOSE[@]}" exec -T -e PGPASSWORD postgres "$@"
}

if ! exec_postgres pg_isready -U "${DB_USER}" -d "${DB_NAME}" >/dev/null 2>&1; then
  echo "[ERRO] Serviço postgres não está acessível via docker compose (${COMPOSE_FILE})." >&2
  echo "       Verifique se a VM está ligada e se o container berkanan-postgres-prod está ativo." >&2
  exit 1
fi

install -d -m 700 "${OUTPUT_DIR}"

echo "=== 1. Exportando vw_metricas_agregadas_diarias.csv ==="
exec_postgres psql -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1 \
  -c '\copy (SELECT * FROM vw_metricas_agregadas_diarias) TO STDOUT WITH CSV HEADER' \
  > "${OUTPUT_DIR}/vw_metricas_agregadas_diarias.csv"

echo "=== 2. Exportando vw_checagem_limiares_monitoramento.csv ==="
exec_postgres psql -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1 \
  -c '\copy (SELECT * FROM vw_checagem_limiares_monitoramento) TO STDOUT WITH CSV HEADER' \
  > "${OUTPUT_DIR}/vw_checagem_limiares_monitoramento.csv"

echo "=== 3. Exportando metricas_requisicao.sql (pg_dump sem owner/ACL) ==="
exec_postgres pg_dump -U "${DB_USER}" -d "${DB_NAME}" \
  --no-owner --no-acl --table=metricas_requisicao \
  > "${OUTPUT_DIR}/metricas_requisicao.sql"

echo "=== 4. Gerando export_metadata.txt (sem segredos/PII/fotos) ==="
EXPORT_TIMESTAMP_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
GIT_COMMIT_SHA="$(git -C "${REPO_ROOT}" rev-parse HEAD 2>/dev/null || echo "unknown")"

METRICS_ROW_COUNT="$(
  exec_postgres psql -U "${DB_USER}" -d "${DB_NAME}" -t -A -v ON_ERROR_STOP=1 \
    -c 'SELECT COUNT(*) FROM metricas_requisicao;'
)"

MIGRATIONS_COUNT="$(
  exec_postgres psql -U "${DB_USER}" -d "${DB_NAME}" -t -A -v ON_ERROR_STOP=1 \
    -c 'SELECT COUNT(*) FROM schema_migrations;'
)"

cat > "${OUTPUT_DIR}/export_metadata.txt" <<EOF
export_timestamp_utc=${EXPORT_TIMESTAMP_UTC}
git_commit_sha=${GIT_COMMIT_SHA}
app_env=${APP_ENV:-unknown}
postgres_db=${DB_NAME}
metricas_requisicao_rows=${METRICS_ROW_COUNT}
schema_migrations_count=${MIGRATIONS_COUNT}
lgpd_scope=aggregated_views_and_metricas_requisicao_only_no_pii_no_photos_no_secrets
exported_files=vw_metricas_agregadas_diarias.csv,vw_checagem_limiares_monitoramento.csv,metricas_requisicao.sql,export_metadata.txt
EOF

echo "[OK] Exportação LGPD-safe concluída em ${OUTPUT_DIR}:"
echo "     - vw_metricas_agregadas_diarias.csv"
echo "     - vw_checagem_limiares_monitoramento.csv"
echo "     - metricas_requisicao.sql (linhas=${METRICS_ROW_COUNT})"
echo "     - export_metadata.txt (migracoes=${MIGRATIONS_COUNT}, commit=${GIT_COMMIT_SHA})"
