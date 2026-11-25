# Playbook Operacional de Containers Docker para Deploy na Azure (`brazilsouth`)

> **Responsável:** Caio Soares de Andrade (**R6 — Engenheiro DevOps** / **R7 — Engenheiro MLOps**)  
> **Última atualização:** 25/11/2026  
> **Topologia alvo:** VM Linux `Standard_B2als_v2` (`brazilsouth`, `StandardSSD_LRS` 64 GB) + Docker Compose + Caddy HTTPS (`berkanan-challenge-2.duckdns.org`) + Azure Static Web Apps (`Free`) — [ADR-009 (Proposto)](../../docs/adr/adr_009.md)

Este playbook organiza **o que precisa estar pronto nos containers Docker** e na operação FinOps (*Azure for Students*) para colocar o **Challenge 2 Berkanan** no ar na Azure com estabilidade para testes 4G e para a avaliação com usuários (#34, prevista para **30/11–02/12**), respeitando o saldo remanescente de créditos (~US$ 46).

---

## 1. Status Atual e Fases de Subida (25/11 → 07/12)

| Fase | Gatilho no Repositório | O que muda nos Containers | Pronto para subir? |
|---|---|---|---|
| **Fase 0 — Base Infra (`infra/devops-mlops-azure`)** | Concluída no **PR #46** | 4 containers (`caddy`, `backend`, `postgres`, `chromadb`), TLS automático, `migrate.sh`, ingestão ChromaDB (`base_conhecimento_v2`) e volume `model_cache` | **CONCLUÍDA NO PR #46** |
| **Fase 1 — Agente Real + Anexo XVI + Tesseract (Estado Atual da `main` `9af6402`)** | **PRs #40–#45 todos mergeados na `main`** | **Otimizar `backend/Dockerfile`** (PyTorch CPU-only + pré-download do modelo multilíngue correto; Seção 3.1 / Issue **#47**) antes do deploy definitivo na VM | **PRÓXIMO PASSO IMEDIATO (#47)** |
| **Fase 2 — Motor OCR Definitivo** | Decisão da **Issue #24** (benchmark Tesseract vs PaddleOCR, pós 27/11) | Manter apenas `tesseract-ocr` ou trocar dependências de sistema/cache para `paddleocr` (Seção 3.2) | Pós-decisão de R3 |
| **Fase 3 — Interface Mobile First** | Entrega do projeto React/Vite em `frontend/` por R5 (**Issue #48**) | Publicar no **Azure Static Web Apps** (padrão) ou servir `dist/` via container/Caddy (Plano B, Seção 3.3) | Pós-entrega de R5 |

---

## 2. Mapa Técnico e Orçamento de Recursos na VM (`Standard_B2als_v2`: 2 vCPU AMD EPYC, 4 GB RAM + 4 GB Swap, 64 GB Standard SSD)

| Container | Imagem / Build | Rede / Portas | Volumes Persistentes | Usuário | Consumo Estimado (RAM / Disco) | Papel na Arquitetura |
|---|---|---|---|---|---|---|
| `berkanan-caddy` | `caddy:2.8.4-alpine` | `80:80`, `443:443` (público) → `backend:8000` | `caddy_data`, `caddy_config` | root (padrão Caddy para bind 80/443) | ~30–60 MB RAM / ~50 MB | Terminação TLS (Let's Encrypt em `berkanan-challenge-2.duckdns.org`), CORS, `max_size 512KB` |
| `berkanan-backend-prod` | `./backend/Dockerfile` (`berkanan/challenge2-backend:prod`) | `expose: 8000` (apenas rede `berkanan_internal`) | `model_cache` → `/home/appuser/.cache` | `appuser` (`10001:10001`) | ~800 MB–1,1 GB RAM (1 worker + embeddings + Tesseract) / ~1,1 GB (CPU-only) | FastAPI (`main:api`), LangGraph, OCR e RAG |
| `berkanan-postgres-prod` | `postgres:16.4-alpine` | `5432` interna (bloqueada no NSG) | `postgres_data` → `/var/lib/postgresql/data` | `postgres` | ~150–250 MB RAM / ~300 MB | TACO, limites IN 75, fontes, cache, `metricas_requisicao` |
| `berkanan-chromadb-prod` | `chromadb/chroma:0.5.20` | `8000` interna (bloqueada no NSG) | `chroma_data` → `/chroma/chroma` | padrão Chroma | ~250–450 MB RAM / ~300 MB | Índice vetorial `base_conhecimento_v2` (SQLite em SSD local) |

> [!IMPORTANT]
> **Por que `Standard_B2als_v2` + `StandardSSD_LRS` + Auto-Shutdown (FinOps Azure for Students)?**  
> Com ~54% da cota de US$ 100 já utilizada (restando ~US$ 46 até 07/12), `Standard_B2als_v2` (mesmo SKU AMD EPYC homologado no Challenge 1, **~US$ 0,038–0,058/h**) reduz drasticamente o gasto mantendo 4 GB de RAM + 4 GB de swap. Com PyTorch CPU-only e `--workers 1`, a stack opera em **~1,7–1,9 GB de RAM**. Somando auto-shutdown diário às 23:00 BRT (`02:00 UTC`) e `az vm deallocate` fora de uso (~70–80h ativas em 12 dias), o gasto total estimado até 07/12 fica em **~US$ 7 a US$ 10**.

> [!IMPORTANT]
> **Reaproveitamento da VM do Challenge 1 (`berkanan`, `northcentralus`):** para evitar cobrança paralela e economizar créditos, a VM `berkanan` (`Standard_B2als_v2`, ~29 GB de disco + `2 GB` de swap, IP `172.183.22.39`) pode ser reaproveitada parando os containers antigos, desativando `--restart` e movendo `~/challenge_1_berkanan` para `~/archive/challenge_1_berkanan` (preservando volumes). Caso decida provisionar uma VM nova em `rg-berkanan-staging`, desaloque ou exclua o grupo `berkanan` antes.

> [!IMPORTANT]
> **Por que usar DuckDNS (`berkanan-challenge-2.duckdns.org`) em vez de `*.brazilsouth.cloudapp.azure.com`?**  
> O sufixo compartilhado `brazilsouth.cloudapp.azure.com` atinge com frequência o limite semanal global do Let's Encrypt (*50 certificados por domínio registrado na Public Suffix List*). Já cada subdomínio gratuito em `duckdns.org` possui cota isolada própria na PSL, garantindo emissão imediata do certificado TLS pelo Caddy sem custo.

---

## 3. Ajustes Obrigatórios de Dockerfile por Gatilho de Merge

### 3.1 Gatilho 1 — Otimização pós-PR #40 (Issue #47, próximo passo imediato)
A `main` atual (`9af6402`) já inclui `sentence-transformers>=3.3.1` em `backend/requirements.txt` e o pré-download de `all-MiniLM-L6-v2` no `backend/Dockerfile`. **Antes do deploy definitivo na VM Azure**, aplique o PR curto da **Issue #47** ajustando `backend/Dockerfile`:
1. Sem `--index-url https://download.pytorch.org/whl/cpu`, o `pip` baixa pacotes **CUDA (~3,5–4,5 GB extras)** desnecessários na VM sem GPU.
2. A coleção `base_conhecimento_v2` usa `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (não `all-MiniLM-L6-v2`).

**Modelo recomendado de `backend/Dockerfile` (Tesseract + CPU-only + cache alinhado):**

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

# Manter 1 worker na Standard_B2als_v2 para não multiplicar RAM do modelo de embeddings
CMD ["uvicorn", "main:api", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

### 3.2 Gatilho 2 — Após a decisão do OCR (Issue #24, pós 27/11)
- **Se Tesseract vencer:** manter `tesseract-ocr tesseract-ocr-por tesseract-ocr-eng` (leve, ~40 MB, cabe tranquilamente nos 4 GB da `Standard_B2s`).
- **Se PaddleOCR vencer:**
  1. Remover `tesseract-ocr*` e instalar apenas `libgl1 libglib2.0-0 libgomp1`.
  2. Pré-baixar os modelos `lang='pt'` no build (ou gravar em `/home/appuser/.paddlex` / volume `model_cache`).
  3. Caso o uso de RAM ultrapasse 3,3 GB nos testes, redimensionar temporariamente a VM apenas durante os 3 dias da avaliação #34 (`az vm resize -g rg-berkanan-staging -n vm-berkanan-api --size Standard_B2ms`, custo adicional de apenas ~US$ 4 nesses 3 dias).

### 3.3 Gatilho 3 — Entrega do `frontend/` por R5 (Issue #48)
- **Caminho Principal (ADR-009 — Azure Static Web Apps):**
  1. Configurar `VITE_API_BASE_URL=https://berkanan-challenge-2.duckdns.org` no build do SWA.
  2. Definir `CORS_ALLOWED_ORIGIN=https://<seu-app>.azurestaticapps.net` em `infra/azure/.env.prod` e reiniciar o Caddy (`docker compose -f infra/azure/compose.prod.yaml --env-file infra/azure/.env.prod up -d caddy`).
- **Plano B (Contingência 100% Docker na mesma VM, zero CORS):**
  Servir o build estático `dist/` diretamente pelo `Caddyfile` sob `https://berkanan-challenge-2.duckdns.org` (`/api/*` → `backend:8000` e `/*` → `/srv/frontend`).

---

## 4. Runbook Passo a Passo de Subida na Azure

### 4.1 Pré-voo Local (antes de tocar na Azure)
> `ADMIN_CIDR` é **obrigatório** (`provision_azure_cli.sh` para com `exit 1` se estiver vazio ou `0.0.0.0/0`).

```bash
python3 scripts/verify_baseline.py
bash infra/scripts/check_compose.sh
ADMIN_CIDR="$(curl -fsS https://ifconfig.me)/32" bash infra/azure/provision_azure_cli.sh --dry-run
```

### 4.2 Provisionamento na Azure (`brazilsouth`), Budget Alert e Domínio DuckDNS
> **Dica:** como o `az` CLI não precisa estar instalado localmente, você pode rodar os comandos abaixo diretamente no **Azure Cloud Shell** (`shell.azure.com` no navegador, clonando o repo) ou instalando o `az` localmente. Se a *Azure Policy* estudantil bloquear `brazilsouth`, rode com `LOCATION=northcentralus` (região já homologada no Challenge 1).

1. Autentique na conta **Azure for Students** e provisione a VM + NSG + Auto-Shutdown (`02:00 UTC` / `23:00 BRT`) + Static Web Apps:
   ```bash
   az login
   ADMIN_CIDR="$(curl -fsS https://ifconfig.me)/32" bash infra/azure/provision_azure_cli.sh --apply
   ```
2. **Configurar Alerta de Orçamento (*Budget Alert* de US$ 20):**
   No Portal Azure → **Cost Management + Billing → Budgets → Add**:
   - Escopo: `rg-berkanan-staging` | Valor: **US$ 20** | Alertas: **50%, 80% e 100%** para o seu e-mail `@aluno.unb.br`.
3. **Apontar o Domínio Gratuito no DuckDNS (leva 30 segundos):**
   - Obtenha o IP público estático criado:
     ```bash
     az vm list-ip-addresses -g rg-berkanan-staging -n vm-berkanan-api --query "[0].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv
     ```
   - Acesse `https://www.duckdns.org` (login via GitHub), crie o subdomínio `berkanan-challenge-2` apontando para esse IP e valide a propagação **antes** de subir o Caddy:
     ```bash
     nslookup berkanan-challenge-2.duckdns.org
     ```

### 4.3 Preparação Única da VM Ubuntu 24.04 LTS
Conecte via SSH (`ssh azureuser@berkanan-challenge-2.duckdns.org`) e execute uma única vez:

```bash
# 1. Instalar Docker Engine + Docker Compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker

# 2. Criar swap de 4 GB (margem de segurança para Standard_B2s durante builds/ingestão)
sudo fallocate -l 4G /swapfile
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

Campos que **precisam** ser conferidos/preenchidos em `infra/azure/.env.prod`:
- `API_DOMAIN=berkanan-challenge-2.duckdns.org`
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
curl -fsS https://berkanan-challenge-2.duckdns.org/health | python3 -m json.tool

# 3. Smoke test externo apontando para o domínio HTTPS
API_BASE_URL=https://berkanan-challenge-2.duckdns.org bash scripts/smoke_backend.sh

# 4. Conferir migrações aplicadas e tabela de métricas no PostgreSQL
docker compose -f infra/azure/compose.prod.yaml --env-file infra/azure/.env.prod exec postgres \
  psql -U berkanan_user -d berkanan_prod -c "SELECT version, applied_at FROM schema_migrations ORDER BY version;"

docker compose -f infra/azure/compose.prod.yaml --env-file infra/azure/.env.prod exec postgres \
  psql -U berkanan_user -d berkanan_prod -c "SELECT * FROM vw_metricas_agregadas_diarias;"
```

### 4.5 Ativar Deploy Contínuo Controlado (GitHub Actions)
No repositório GitHub → **Settings → Environments → New environment**: `azure-staging`.
Adicione os 4 secrets obrigatórios consumidos por [`.github/workflows/deploy-azure.yml`](../../.github/workflows/deploy-azure.yml):
- `AZURE_VM_HOST`: `berkanan-challenge-2.duckdns.org`
- `AZURE_VM_USER`: `azureuser`
- `AZURE_VM_SSH_KEY`: chave privada SSH dedicada ao deploy
- `AZURE_DEPLOY_PATH`: `/opt/berkanan/Challenge2_berkanan`

---

## 5. Rotina FinOps (Desalocação), Backup e Descomissionamento Pós-07/12

### 5.1 Desalocar e Religar a VM (Economia de Créditos *Azure for Students*)
A VM já possui desligamento/desalocação automática às **23:00 BRT (`02:00 UTC`)**. Fora das janelas de teste/avaliação:
> **Atenção:** rodar `sudo shutdown` dentro do Linux **não** para a cobrança da VM (status `Stopped`). Use sempre `az vm deallocate` ou o botão **Stop** do Portal Azure (status `Stopped (deallocated)`).

```bash
# Pausar cobrança de CPU/RAM imediatamente (os volumes Docker permanecem intactos no SSD):
az vm deallocate -g rg-berkanan-staging -n vm-berkanan-api

# Religar antes de testes 4G ou sessões com usuários (~60s; os containers sobem sozinhos por restart: unless-stopped):
az vm start -g rg-berkanan-staging -n vm-berkanan-api
```
> *Obs.: caso seu IP residencial mude em outro dia e você precise abrir SSH, atualize a regra `AllowSSHAdmin`:*  
> `az network nsg rule update -g rg-berkanan-staging --nsg-name nsg-berkanan-api -n AllowSSHAdmin --source-address-prefixes "$(curl -fsS https://ifconfig.me)/32"`

### 5.2 Regras de Ouro na VM e Backup `pg_dump`
- **NUNCA rode `docker compose down -v` na Azure:** além de apagar `postgres_data` e `chroma_data`, apaga `caddy_data` e força nova emissão de certificado TLS.
- **Para atualizar a stack:** `bash infra/azure/bootstrap_stack.sh` (ou workflow `Deploy Azure Staging`).
- **Para forçar reindexação do ChromaDB:** `FORCE_REINDEX=1 bash infra/azure/bootstrap_stack.sh`.
- **Backup do PostgreSQL (rodar após as sessões da #34 e antes do teardown de 07/12):**
  ```bash
  mkdir -p /opt/berkanan/backups
  docker compose -f infra/azure/compose.prod.yaml --env-file infra/azure/.env.prod exec -T postgres \
    pg_dump -U berkanan_user -d berkanan_prod | gzip > "/opt/berkanan/backups/berkanan_$(date +%F_%H%M).sql.gz"
  ```

### 5.3 Descomissionamento Integral Pós-Apresentação (após 07/12/2026)
Logo após a entrega final da disciplina em **07/12/2026**:
1. Copie o backup final `.sql.gz` e o export das views `vw_*` da VM para sua máquina local (`scp`).
2. Remova todo o grupo de recursos para zerar 100% do consumo de disco/IP na conta *Azure for Students*:
   ```bash
   az group delete --name rg-berkanan-staging --yes
   ```

---

## 6. Diagnóstico Rápido de Problemas Comuns

| Sintoma | Causa Provável | Ação Imediata |
|---|---|---|
| `provision_azure_cli.sh` para logo no início | `ADMIN_CIDR` ausente, inválido ou `0.0.0.0/0` | Passar `ADMIN_CIDR="$(curl -fsS https://ifconfig.me)/32"` |
| Backend reinicia com `exit code 137` | Falta de RAM (OOM) por imagem sem CPU-only ou múltiplos workers | Garantir swap de 4 GB (`free -h`), `--workers 1` e imagem PyTorch CPU-only (Seção 3.1) |
| `https://berkanan-challenge-2.duckdns.org` sem TLS | IP ainda não apontado no DuckDNS ou VM estava desalocada | Verificar `nslookup berkanan-challenge-2.duckdns.org`, `az vm start` e `logs caddy` |
| HTTP `413 Payload Too Large` no celular | Foto enviada acima de `512KB` (`CADDY_MAX_BODY_SIZE`) | Validar compressão mobile (~1280 px, JPEG ≤ 300 KB) no frontend |
| Erro `blocked by CORS policy` no navegador | `CORS_ALLOWED_ORIGIN` diferente da URL exata do frontend (ou com `/` final) | Ajustar `CORS_ALLOWED_ORIGIN` sem `/` final em `.env.prod` e rodar `up -d caddy` |
| Câmera não abre no navegador mobile | Frontend acessado via `http://` em vez de `https://` | Garantir acesso via HTTPS (Static Web Apps ou `https://berkanan-challenge-2.duckdns.org`) |
| `/health` retorna `degraded` no ChromaDB | Coleção `base_conhecimento_v2` vazia | Rodar `FORCE_REINDEX=1 bash infra/azure/bootstrap_stack.sh` |
