# Playbook Operacional de Containers Docker para Deploy na Azure (`brazilsouth`)

> **Responsável:** Caio Soares de Andrade (**R6 — Engenheiro DevOps** / **R7 — Engenheiro MLOps**)  
> **Última atualização:** 24/11/2026  
> **Topologia alvo:** VM Linux `Standard_B2ms` (`brazilsouth`) com Docker Compose + Caddy HTTPS + Azure Static Web Apps (`Free`) — [ADR-009 (Proposto)](../../docs/adr/adr_009.md)

Este playbook organiza **o que precisa estar pronto nos containers Docker** antes, durante e depois dos merges pendentes do time para colocar o **Challenge 2 Berkanan** no ar na Azure com estabilidade para testes 4G e para a avaliação com usuários (#34, prevista para **30/11–02/12**).

---

## 1. Status Atual e Fases de Subida (24/11 → 07/12)

| Fase | Gatilho no Repositório | O que muda nos Containers | Pronto para subir? |
|---|---|---|---|
| **Fase 0 — Base Infra (`main` + `infra/devops-mlops-azure`)** | Merge desta branch na `main` | 4 containers (`caddy`, `backend`, `postgres`, `chromadb`), TLS automático, `migrate.sh`, ingestão ChromaDB (`base_conhecimento_v2`) e volume `model_cache` | **SIM** (API ainda com agente nutricional simulado até #40 entrar) |
| **Fase 1 — Agente Real + Gemini + Tesseract** | Merge do **PR #40** (`feat/api-r5`) e **PR #45** (`feat/anexo-xvi`) | **Otimizar `backend/Dockerfile`** (PyTorch CPU-only + pré-download do modelo multilíngue correto; detalhes na Seção 3.1) | Após merge + PR rápido de otimização Docker |
| **Fase 2 — Motor OCR Definitivo** | Decisão da **Issue #24** (benchmark Tesseract vs PaddleOCR, pós 27/11) | Manter apenas `tesseract-ocr` ou trocar dependências de sistema/cache para `paddleocr` (Seção 3.2) | Pós-decisão de R3 |
| **Fase 3 — Interface Mobile First** | Entrega do projeto React/Vite em `frontend/` por R5 | Publicar no **Azure Static Web Apps** (padrão) ou servir `dist/` via container/Caddy (Plano B, Seção 3.3) | Pós-entrega de R5 |

---

## 2. Mapa Técnico e Orçamento de Recursos na VM (`Standard_B2ms`: 2 vCPU, 8 GB RAM, 64 GB SSD)

| Container | Imagem / Build | Rede / Portas | Volumes Persistentes | Usuário | Consumo Estimado (RAM / Disco) | Papel na Arquitetura |
|---|---|---|---|---|---|---|
| `berkanan-caddy` | `caddy:2.8.4-alpine` | `80:80`, `443:443` (público) → `backend:8000` | `caddy_data`, `caddy_config` | root (padrão Caddy para bind 80/443) | ~30–60 MB RAM / ~50 MB | Terminação TLS (Let's Encrypt), CORS, `max_size 512KB` |
| `berkanan-backend-prod` | `./backend/Dockerfile` (`berkanan/challenge2-backend:prod`) | `expose: 8000` (apenas rede `berkanan_internal`) | `model_cache` → `/home/appuser/.cache` | `appuser` (`10001:10001`) | ~450 MB–1,2 GB RAM (com embeddings/OCR) / ~1,1 GB (CPU-only) | FastAPI (`main:api`), LangGraph, OCR e RAG |
| `berkanan-postgres-prod` | `postgres:16.4-alpine` | `5432` interna (bloqueada no NSG) | `postgres_data` → `/var/lib/postgresql/data` | `postgres` | ~150–300 MB RAM / ~300 MB | TACO, limites IN 75, fontes, cache, `metricas_requisicao` |
| `berkanan-chromadb-prod` | `chromadb/chroma:0.5.20` | `8000` interna (bloqueada no NSG) | `chroma_data` → `/chroma/chroma` | padrão Chroma | ~300–600 MB RAM / ~300 MB | Índice vetorial `base_conhecimento_v2` (SQLite em SSD local) |

> [!IMPORTANT]
> **Por que removemos `/docker-entrypoint-initdb.d` de `compose.prod.yaml`?**  
> Em produção, `infra/azure/bootstrap_stack.sh` aplica as migrações transacionalmente via `migrations/migrate.sh` (`SEED=0`, com controle em `schema_migrations`). Manter `docker-entrypoint-initdb.d` duplicaria execuções no primeiro boot e exigiria editar `compose.prod.yaml` a cada nova migração (`012+`).

> [!IMPORTANT]
> **Volume `model_cache` no `/home/appuser/.cache`:**  
> Os embeddings ONNX/HuggingFace (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) consomem ~470 MB. O volume `model_cache` (montado também nos containers efêmeros de ingestão em `bootstrap_stack.sh`) evita re-download a cada deploy ou restart.

---

## 3. Ajustes Obrigatórios de Dockerfile por Gatilho de Merge

### 3.1 Gatilho 1 — Logo após o merge do PR #40 (`feat/api-r5`)
O PR #40 adiciona `sentence-transformers>=3.3.1` em `backend/requirements.txt` e faz pré-download de `all-MiniLM-L6-v2` no `backend/Dockerfile`. **Antes de fazer build na VM Azure**, abra um PR curto de R6 ajustando `backend/Dockerfile` pelos dois motivos críticos abaixo:
1. Sem `--index-url https://download.pytorch.org/whl/cpu`, o `pip` baixa o **PyTorch com CUDA (~3,5–4,5 GB extras)** desnecessários na VM sem GPU.
2. A coleção `base_conhecimento_v2` usa `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (não `all-MiniLM-L6-v2`).

**Modelo recomendado de `backend/Dockerfile` pós-PR #40 (Tesseract + CPU-only + cache alinhado):**

```dockerfile
FROM python:3.12.7-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/home/appuser/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/home/appuser/.cache/sentence-transformers \
    CHROMA_CACHE_DIR=/home/appuser/.cache/chroma \
    APP_ENV=development \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-por tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 appgroup && \
    useradd --uid 10001 --gid appgroup --shell /usr/sbin/nologin --create-home appuser

# Instala PyTorch CPU-only antes de requirements.txt para evitar baixar pacotes CUDA (~4 GB)
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

RUN mkdir -p /home/appuser/.cache/huggingface /home/appuser/.cache/sentence-transformers /home/appuser/.cache/chroma && \
    chown -R appuser:appgroup /home/appuser/.cache

USER appuser

# Pré-aquece o modelo multilíngue real usado pela base_conhecimento_v2 (com fallback seguro offline)
RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')" \
    || echo "Aviso: modelo sera carregado sob demanda no startup/volume model_cache."

COPY --chown=appuser:appgroup . /app/

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/openapi.json', timeout=3)" || exit 1

# Manter 1 worker na Standard_B2ms para não multiplicar RAM do modelo de embeddings
CMD ["uvicorn", "main:api", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

> [!TIP]
> Se o time confirmar no código que `backend/chroma_client.py` continuará usando apenas ONNX Runtime (sem `sentence-transformers` em runtime), basta manter `requirements.txt` sem `sentence-transformers` para uma imagem ainda menor (~500 MB). Caso `sentence-transformers` permaneça, o bloco `torch` CPU-only acima é obrigatório na VM `Standard_B2ms`.

### 3.2 Gatilho 2 — Após a decisão do OCR (Issue #24, pós 27/11)
- **Se Tesseract vencer:** manter `tesseract-ocr tesseract-ocr-por tesseract-ocr-eng` (leve, ~40 MB, baixo uso de RAM).
- **Se PaddleOCR vencer:**
  1. Remover `tesseract-ocr*` e instalar apenas as bibliotecas de sistema mínimas do OpenCV/Paddle: `libgl1 libglib2.0-0 libgomp1`.
  2. Pré-baixar os modelos `lang='pt'` no build (ou garantir gravação em `/home/appuser/.paddlex` / volume `model_cache`), evitando download no primeiro request de usuário no 4G.
  3. Monitorar RAM com `docker stats`: o PaddleOCR adiciona ~600–900 MB em memória; com `swap` de 2 GB configurado na VM (Seção 4.3), a `Standard_B2ms` (8 GB) suporta com folga.

### 3.3 Gatilho 3 — Entrega do `frontend/` (R5)
- **Caminho Principal (ADR-009 — Azure Static Web Apps):**
  1. Configurar `VITE_API_BASE_URL=https://berkanan-api.brazilsouth.cloudapp.azure.com` no build do SWA.
  2. Definir `CORS_ALLOWED_ORIGIN=https://<seu-app>.azurestaticapps.net` em `infra/azure/.env.prod` e reiniciar o Caddy (`docker compose -f infra/azure/compose.prod.yaml --env-file infra/azure/.env.prod up -d caddy`).
- **Plano B (Contingência 100% Docker na mesma VM, zero CORS):**
  Se precisar colocar no ar em minutos sem aguardar pipeline do Static Web Apps, adicione um `frontend/Dockerfile` multi-stage (`node:20-alpine` gerando `dist/` → `caddy:2.8.4-alpine` ou volume compartilhado) e faça o `Caddyfile` servir `/api/*` para `backend:8000` e `/*` para `/srv/frontend` (`try_files {path} /index.html`).

---

## 4. Runbook Passo a Passo de Subida na Azure

### 4.1 Pré-voo Local (antes de tocar na Azure)
```bash
python3 scripts/verify_baseline.py
bash infra/scripts/check_compose.sh
ADMIN_CIDR="SEU_IP_PUBLICO/32" bash infra/azure/provision_azure_cli.sh --dry-run
```

### 4.2 Provisionamento na Azure (`brazilsouth`) e Validação de DNS
1. Autentique e provisione a VM + NSG + IP estático + Static Web Apps:
   ```bash
   az login
   ADMIN_CIDR="SEU_IP_PUBLICO/32" bash infra/azure/provision_azure_cli.sh --apply
   ```
2. **Checagem obrigatória antes de subir o Caddy:** confirme que o DNS público já resolve para o IP da VM (senão o desafio HTTP-01 do Let's Encrypt falha):
   ```bash
   nslookup berkanan-api.brazilsouth.cloudapp.azure.com
   ```

### 4.3 Preparação Única da VM Ubuntu 24.04 LTS
Conecte via SSH (`ssh azureuser@berkanan-api.brazilsouth.cloudapp.azure.com`) e execute uma única vez:

```bash
# 1. Instalar Docker Engine + Docker Compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker

# 2. Criar swap preventivo de 2 GB (proteção contra picos de build/PaddleOCR)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 3. Clonar repositório no diretório padrão de deploy
sudo mkdir -p /opt/berkanan && sudo chown -R "$USER":"$USER" /opt/berkanan
git clone https://github.com/unb-Sistemas-de-Machine-learning/Challenge2_berkanan.git /opt/berkanan/Challenge2_berkanan
cd /opt/berkanan/Challenge2_berkanan

# 4. Configurar segredos reais (NUNCA commitar .env.prod)
cp infra/azure/.env.prod.example infra/azure/.env.prod
chmod 600 infra/azure/.env.prod
nano infra/azure/.env.prod
```

Campos que **precisam** ser alterados em `infra/azure/.env.prod`:
- `API_DOMAIN=berkanan-api.brazilsouth.cloudapp.azure.com`
- `CORS_ALLOWED_ORIGIN=https://<url-do-static-web-app>.azurestaticapps.net`
- `POSTGRES_PASSWORD=<senha-forte-gerada>`
- `GEMINI_API_KEY=<sua-chave-gemini>`
- `LLM_MODEL=<modelo-definido-pela-equipe>`

### 4.4 Primeira Subida e Verificação Ponta a Ponta
```bash
cd /opt/berkanan/Challenge2_berkanan
bash infra/azure/bootstrap_stack.sh
```

Verificações obrigatórias logo após o bootstrap:
```bash
# 1. Status dos 4 containers
docker compose -f infra/azure/compose.prod.yaml --env-file infra/azure/.env.prod ps

# 2. Healthcheck público em HTTPS (valida TLS Let's Encrypt + Caddy + Backend + Postgres + ChromaDB)
curl -fsS https://berkanan-api.brazilsouth.cloudapp.azure.com/health | python3 -m json.tool

# 3. Smoke test externo apontando para o domínio HTTPS
API_BASE_URL=https://berkanan-api.brazilsouth.cloudapp.azure.com bash scripts/smoke_backend.sh

# 4. Conferir migrações aplicadas e tabela de métricas no PostgreSQL
docker compose -f infra/azure/compose.prod.yaml --env-file infra/azure/.env.prod exec postgres \
  psql -U berkanan_user -d berkanan_prod -c "SELECT version, applied_at FROM schema_migrations ORDER BY version;"

docker compose -f infra/azure/compose.prod.yaml --env-file infra/azure/.env.prod exec postgres \
  psql -U berkanan_user -d berkanan_prod -c "SELECT * FROM vw_metricas_agregadas_diarias;"
```

### 4.5 Ativar Deploy Contínuo Controlado (GitHub Actions)
No repositório GitHub → **Settings → Environments → New environment**: `azure-staging`.
Adicione os 4 secrets obrigatórios consumidos por [`.github/workflows/deploy-azure.yml`](../../.github/workflows/deploy-azure.yml):
- `AZURE_VM_HOST`: `berkanan-api.brazilsouth.cloudapp.azure.com`
- `AZURE_VM_USER`: `azureuser`
- `AZURE_VM_SSH_KEY`: chave privada SSH dedicada ao deploy
- `AZURE_DEPLOY_PATH`: `/opt/berkanan/Challenge2_berkanan`

---

## 5. Regras Críticas de Operação, Backup e Troubleshooting

### Regras de Ouro na VM
- **NUNCA rode `docker compose down -v` na Azure:** além de apagar `postgres_data` e `chroma_data`, apaga `caddy_data` e força reemissão de certificado TLS (Let's Encrypt limita a 5 certificados idênticos por semana).
- **Para atualizar a stack:** use sempre `bash infra/azure/bootstrap_stack.sh` (ou dispare o workflow `Deploy Azure Staging`).
- **Para forçar reindexação da base RAG (ex.: `base_conhecimento_v3`):**
  ```bash
  FORCE_REINDEX=1 bash infra/azure/bootstrap_stack.sh
  ```
- **Limpeza segura de disco (sem tocar em volumes):**
  ```bash
  docker image prune -f && docker builder prune --filter "until=72h" -f
  ```

### Backup Rápido do PostgreSQL (rodar antes da avaliação #34 e antes de 07/12)
```bash
mkdir -p /opt/berkanan/backups
docker compose -f infra/azure/compose.prod.yaml --env-file infra/azure/.env.prod exec -T postgres \
  pg_dump -U berkanan_user -d berkanan_prod | gzip > "/opt/berkanan/backups/berkanan_$(date +%F_%H%M).sql.gz"
```

### Diagnóstico Rápido de Problemas Comuns

| Sintoma | Causa Provável | Ação Imediata |
|---|---|---|
| Backend reinicia com `exit code 137` | Falta de RAM (OOM) durante download/carga do modelo ou PaddleOCR | Conferir `free -h` (swap ativo), garantir `--workers 1` e imagem PyTorch CPU-only |
| `https://...` não abre / erro TLS no Caddy | DNS ainda não apontava para a VM ou porta `80`/`443` bloqueada no NSG | Verificar `docker compose ... logs caddy`, `nslookup` e regras `AllowHTTP`/`AllowHTTPS` no NSG |
| HTTP `413 Payload Too Large` no celular | Foto enviada acima de `512KB` (`CADDY_MAX_BODY_SIZE`) | Validar compressão mobile (~1280 px, JPEG ≤ 300 KB) no frontend |
| Erro `blocked by CORS policy` no navegador | `CORS_ALLOWED_ORIGIN` diferente da URL exata do frontend (ou barra `/` no final) | Ajustar `CORS_ALLOWED_ORIGIN` sem `/` final em `.env.prod` e rodar `up -d caddy` |
| Câmera não abre no navegador mobile | Frontend acessado via `http://` em vez de `https://` | Garantir acesso via HTTPS (Static Web Apps ou Caddy) |
| `/health` retorna `degraded` no ChromaDB | Coleção `base_conhecimento_v2` vazia ou volume corrompido | Rodar `FORCE_REINDEX=1 bash infra/azure/bootstrap_stack.sh` |
