#!/usr/bin/env bash
# ==============================================================================
# SCRIPT DE MIGRAÇÕES AUTOMATIZADAS: migrate.sh
# FINALIDADE: Permitir que o Caio (ou pipeline CI/CD) recrie e atualize o banco
#             nos ambientes de desenvolvimento (dev) e produção (prod).
# REVISÃO 14/11:
#   - Só aplica arquivos numerados (NNN_*.sql) desta pasta.
#   - Dados fictícios ficam em ../seeds e só rodam com SEED=1 (uso em dev).
#   - Cada migração e seu registro em schema_migrations rodam numa transação só.
# Senha: usar a variável PGPASSWORD (ou ~/.pgpass), combinada com o Caio.
# ==============================================================================

set -euo pipefail

# Configurações de conexão (podem ser sobrescritas por variáveis de ambiente)
DB_HOST="${DB_HOST:-${POSTGRES_HOST:-localhost}}"
DB_PORT="${DB_PORT:-${POSTGRES_PORT:-5432}}"
DB_NAME="${DB_NAME:-${POSTGRES_DB:-berkanan_dev}}"
DB_USER="${DB_USER:-${POSTGRES_USER:-berkanan_user}}"
SEED="${SEED:-0}"

MIGRATIONS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEEDS_DIR="${MIGRATIONS_DIR}/../seeds"

PSQL=(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1)

echo "=== INICIANDO MIGRAÇÕES PARA: ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME} ==="

# 1. Cria tabela de controle de migrações se não existir
"${PSQL[@]}" -q -c "CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(100) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);"

aplicar() {
    local file="$1" version="$2"
    local already_applied
    already_applied=$("${PSQL[@]}" -t -A -c \
        "SELECT COUNT(*) FROM schema_migrations WHERE version = '${version}';")
    if [ "${already_applied}" -eq 0 ]; then
        echo "--> Aplicando: ${version}..."
        # Arquivo + registro na mesma transação: se falhar, nada fica pela metade
        "${PSQL[@]}" --single-transaction -f "${file}" \
            -c "INSERT INTO schema_migrations (version) VALUES ('${version}');"
        echo "    ✓ ${version} aplicada com sucesso!"
    else
        echo "    - ${version} já foi aplicada anteriormente. Pulando."
    fi
}

# 2. Migrações numeradas, em ordem
for file in $(find "${MIGRATIONS_DIR}" -maxdepth 1 -name "[0-9][0-9][0-9]_*.sql" | sort); do
    aplicar "${file}" "$(basename "${file}")"
done

# 3. Seeds fictícios: só em dev, com SEED=1
if [ "${SEED}" = "1" ]; then
    for file in $(find "${SEEDS_DIR}" -maxdepth 1 -name "*.sql" | sort); do
        aplicar "${file}" "seeds/$(basename "${file}")"
    done
else
    echo "(Seeds não aplicados. Em dev, use SEED=1 para carregar dados fictícios.)"
fi

echo "=== TODAS AS MIGRAÇÕES FORAM EXECUTADAS COM SUCESSO! ==="
