
#!/usr/bin/env bash
# Smoke tests para o backend FastAPI (POST /api/analyze).
# Valida o contrato da API e a classificação determinística da rotulagem.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
API_BASE_URL="${API_BASE_URL:-http://${API_HOST}:${API_PORT}}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

SERVER_PID=""
TMP_DIR="$(mktemp -d)"

cleanup() {
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    kill "${SERVER_PID}" 2>/dev/null || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

is_api_up() {
  curl -fsS "${API_BASE_URL}/openapi.json" >/dev/null 2>&1
}

if ! is_api_up; then
  echo "[INFO] API não detectada em ${API_BASE_URL}. Iniciando uvicorn local temporário..."
  (
    cd "${REPO_ROOT}/backend"
    exec "${PYTHON_BIN}" -m uvicorn main:api --host "${API_HOST}" --port "${API_PORT}" >"${TMP_DIR}/uvicorn.log" 2>&1
  ) &
  SERVER_PID=$!

  for _ in $(seq 1 30); do
    if is_api_up; then
      break
    fi
    sleep 0.5
  done

  if ! is_api_up; then
    echo "[ERRO] A API não iniciou dentro do tempo limite. Logs do Uvicorn:" >&2
    cat "${TMP_DIR}/uvicorn.log" >&2 || true
    exit 1
  fi

  echo "[OK] API iniciada com sucesso (PID ${SERVER_PID})."
else
  echo "[INFO] Utilizando API já em execução em ${API_BASE_URL}."
fi

run_case() {
  local case_name="$1"
  local enable_verifier="$2"
  local response_file="${TMP_DIR}/response_${enable_verifier}.json"

  echo "=== Caso: ${case_name} (enable_verifier=${enable_verifier}) ==="

  local http_code
  http_code="$(
    curl -sS -o "${response_file}" -w "%{http_code}" \
      -X POST "${API_BASE_URL}/api/analyze" \
      -H "Content-Type: application/json" \
      -d "{
        \"request_type\": \"ocr_analysis\",
        \"enable_verifier\": ${enable_verifier},
        \"user_profile\": {
          \"has_diabetes\": true,
          \"has_hypertension\": false
        },
        \"valores_nutricionais_100\": {
          \"acucares_adicionados\": 16,
          \"gorduras_saturadas\": 2,
          \"sodio\": 500
        },
        \"tipo_alimento\": \"solido\",
        \"categoria_produto\": \"outro\"
      }"
  )"

  if [[ "${http_code}" != "200" ]]; then
    echo "[FALHA] Código HTTP esperado 200, recebido ${http_code}." >&2
    cat "${response_file}" >&2 || true
    exit 1
  fi

  "${PYTHON_BIN}" - "${response_file}" "${enable_verifier}" <<'PYEOF'
import json
import sys
from pathlib import Path

resp_path = Path(sys.argv[1])
enable_verifier = sys.argv[2].lower() == "true"

try:
    payload = json.loads(resp_path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"[FALHA] Resposta não é um JSON válido: {exc}", file=sys.stderr)
    sys.exit(1)

required_fields = [
    "input_text",
    "llm_explanation",
    "matched_sources",
    "timestamp",
    "response_time_ms",
    "classification",
    "confidence_score",
    "rag_sources_count",
    "warnings",
    "verification",
    "rotulagem",
]

missing = [field for field in required_fields if field not in payload]
if missing:
    print(f"[FALHA] Campos obrigatórios ausentes: {missing}", file=sys.stderr)
    sys.exit(1)

# matched_sources pode estar vazio porque esta classificação
# utiliza regras determinísticas, sem depender de RAG.
if not isinstance(payload["matched_sources"], list):
    print("[FALHA] matched_sources deveria ser uma lista.", file=sys.stderr)
    sys.exit(1)

if not isinstance(payload["response_time_ms"], int) or payload["response_time_ms"] < 0:
    print(f"[FALHA] response_time_ms inválido: {payload['response_time_ms']!r}", file=sys.stderr)
    sys.exit(1)

if not isinstance(payload["rag_sources_count"], int) or payload["rag_sources_count"] < 0:
    print(f"[FALHA] rag_sources_count inválido: {payload['rag_sources_count']!r}", file=sys.stderr)
    sys.exit(1)

if payload["classification"] not in {
    "SAUDAVEL", "ATENCAO", "EVITAR", "INCONCLUSIVO", "ERRO"
}:
    print(f"[FALHA] classification fora do contrato: {payload['classification']!r}", file=sys.stderr)
    sys.exit(1)

# Valida a classificação determinística da rotulagem.
rotulagem = payload.get("rotulagem")

if not isinstance(rotulagem, dict):
    print("[FALHA] Objeto rotulagem deveria estar presente.", file=sys.stderr)
    sys.exit(1)

if rotulagem.get("status") != "ok":
    print(f"[FALHA] Status inesperado em rotulagem: {rotulagem.get('status')!r}", file=sys.stderr)
    sys.exit(1)

if rotulagem.get("categoria_produto") != "outro":
    print(f"[FALHA] Categoria inesperada: {rotulagem.get('categoria_produto')!r}", file=sys.stderr)
    sys.exit(1)

if rotulagem.get("tipo") != "solido":
    print(f"[FALHA] Tipo de alimento inesperado: {rotulagem.get('tipo')!r}", file=sys.stderr)
    sys.exit(1)

if "acucares_adicionados" not in rotulagem.get("alto_em", []):
    print(
        f"[FALHA] Açúcares adicionados deveriam ser ALTO EM: "
        f"{rotulagem.get('alto_em')!r}",
        file=sys.stderr,
    )
    sys.exit(1)

if rotulagem.get("fonte") != "IN 75/2020, Anexo XV":
    print(f"[FALHA] Fonte normativa inesperada: {rotulagem.get('fonte')!r}", file=sys.stderr)
    sys.exit(1)

# Valida o comportamento do verificador.
if enable_verifier:
    verification = payload.get("verification")

    if not isinstance(verification, dict):
        print("[FALHA] verification deveria ser um objeto quando enable_verifier=true.", file=sys.stderr)
        sys.exit(1)

    if verification.get("passed") is not True or not isinstance(verification.get("errors"), list):
        print(f"[FALHA] Conteúdo inesperado em verification: {verification!r}", file=sys.stderr)
        sys.exit(1)
else:
    if payload.get("verification") is not None:
        print(
            f"[FALHA] verification deveria ser null quando enable_verifier=false, "
            f"recebido: {payload.get('verification')!r}",
            file=sys.stderr,
        )
        sys.exit(1)

print(
    f"  [OK] HTTP 200 | ALTO EM={rotulagem['alto_em']} | "
    f"RAG={payload['rag_sources_count']} | "
    f"verification={'presente' if payload['verification'] is not None else 'null'}"
)
PYEOF
}

run_case "Teste 1 — Verificador Habilitado" "true"
run_case "Teste 2 — Verificador Desabilitado" "false"

echo "[SUCESSO] Todos os smoke tests da API passaram."
