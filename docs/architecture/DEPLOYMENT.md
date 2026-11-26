# Arquitetura de Deploy, Containerização e Requisitos Mobile First

> **Responsável:** Caio Soares de Andrade (**R6 — Engenheiro DevOps** / **R7 — Engenheiro MLOps**)  
> **Última atualização:** 25/11/2026  

Este documento detalha a infraestrutura de containers implementada para o **Challenge 2 Berkanan**, tanto para desenvolvimento local ([compose.yaml](../../compose.yaml)) quanto para a proposta de implantação híbrida enxuta na **Microsoft Azure (`brazilsouth`)** ([ADR-009 proposto](../adr/adr_009.md)), diferenciando o que está operacional daquilo que aguarda entrega ou decisão das demais frentes.

---

## 1. Topologia de Containers Local (`compose.yaml`)

```mermaid
flowchart LR
    Mobile["Navegador Mobile (React/Vite - PENDENTE)"] -->|"HTTP :8000 (JSON / JPEG <= 300KB)"| Backend["berkanan-backend (FastAPI + LangGraph)"]
    subgraph Rede Interna Docker ["berkanan_internal (bridge)"]
        Backend -->|"Porta 5432 (backend/database.py)"| Postgres[("berkanan-postgres (PostgreSQL 16.4)")]
        Backend -->|"Porta 8000 interna (backend/chroma_client.py)"| Chroma[("berkanan-chromadb (ChromaDB 0.5.20)")]
    end
    Postgres --- VolPG[("Volume: postgres_data")]
    Chroma --- VolChroma[("Volume: chroma_data")]
```

### 1.1 Serviços Locais Configurados

| Serviço | Imagem / Build | Porta Interna | Porta Host (padrão local) | Volume Persistente | Status da Integração no Código |
|---|---|---|---|---|---|
| `backend` | Build local (`./backend/Dockerfile`, base `python:3.12.7-slim-bookworm`) | `8000` | `127.0.0.1:8000` | Sem estado (stateless) | `IMPLEMENTADO` (`main:api`, `/health`, `/api/analyze`, agente nutricional + RAG + Config. C + OCR pytesseract + `llm_calls` via PR #40) |
| `postgres` | `postgres:16.4-alpine` | `5432` | `127.0.0.1:5432` | `postgres_data` | `IMPLEMENTADO` (migrações `001`–`011` montadas em `/docker-entrypoint-initdb.d`, `database.py`) |
| `chromadb` | `chromadb/chroma:0.5.20` | `8000` | `127.0.0.1:8001` | `chroma_data` | `IMPLEMENTADO` (`chroma_client.py`, `scripts/ingest_chroma.py`, coleção `base_conhecimento_v2`) |
| `frontend` | *Não incluído ainda* | — | — | — | `PENDENTE` (aguardando entrega React/Vite por R5) |

---

## 2. Topologia Híbrida Enxuta na Azure (`infra/azure/` — ADR-009 Proposto)

Para viabilizar os testes em celulares reais via 4G (câmera exige HTTPS) e a avaliação com usuários (#34) dentro do saldo remanescente da conta **Azure for Students** (~US$ 46), a stack de staging/produção utiliza uma **VM Linux em `brazilsouth`** (`Standard_B2als_v2` — 2 vCPU AMD EPYC, 4 GB RAM + 4 GB swap em `StandardSSD_LRS` 64 GB, com auto-shutdown diário às 23h BRT; fallback `northcentralus`), domínio gratuito dedicado **`berkanan-challenge-2.duckdns.org`** e **Azure Static Web Apps (`Free`)**:

```mermaid
flowchart LR
    Celular["Celular 4G (Navegador Mobile)"] -->|"HTTPS :443"| SWA["Azure Static Web Apps (React/Vite - PENDENTE)"]
    Celular -->|"HTTPS :443 (berkanan-challenge-2.duckdns.org <= 512KB)"| Caddy["Caddy 2.8.4 (TLS Let's Encrypt + CORS)"]
    SWA -.->|"CORS_ALLOWED_ORIGIN"| Caddy
    subgraph VM Azure brazilsouth ["VM Standard_B2als_v2 — StandardSSD local (berkanan_internal)"]
        Caddy -->|"HTTP :8000 interno"| Backend["berkanan-backend-prod (FastAPI + LangGraph)"]
        Backend -->|"Porta 5432"| Postgres[("postgres:16.4-alpine (postgres_data)")]
        Backend -->|"Porta 8000"| Chroma[("chromadb:0.5.20 (chroma_data)")]
    end
```

### 2.1 Decisões de Estabilidade, Segurança e FinOps
- **SQLite estável em SSD local:** o **ChromaDB 0.5.20** armazena metadados em SQLite local; o disco `StandardSSD_LRS` da VM evita os problemas de lock de volumes SMB (Azure Files).
- **Domínio dedicado gratuito (`berkanan-challenge-2.duckdns.org`):** o **Caddy** emite certificados **TLS automáticos (Let's Encrypt)** evitando o rate limit compartilhado de `*.brazilsouth.cloudapp.azure.com`, além de aplicar limite `CADDY_MAX_BODY_SIZE=512KB` e CORS.
- **Segurança SSH estrita:** `infra/azure/provision_azure_cli.sh` **para com erro (`exit 1`)** se `ADMIN_CIDR` não for informado ou for aberto (`0.0.0.0/0`), cria a VM com `--authentication-type ssh` (`disablePasswordAuthentication: true`) e bloqueia `5432`, `8000` e `8001` no NSG.
- **FinOps (*Azure for Students*):** estimativa total de **~US$ 7 a US$ 10** até 07/12 combinando `Standard_B2als_v2`, auto-shutdown diário (`02:00 UTC` / `23:00 BRT`), `az vm deallocate` fora de uso, Budget Alert em US$ 20 e `az group delete` pós-07/12.

### 2.2 Passo a Passo de Provisionamento e Deploy na Azure

> **Guia operacional detalhado:** consulte o playbook completo em [infra/azure/PLAYBOOK.md](../../infra/azure/PLAYBOOK.md) para ajustes de `Dockerfile` pós-PR #40/#24, rotina FinOps (`deallocate`/Budget/teardown), configuração do DuckDNS, backup `pg_dump` e troubleshooting.

1. **Provisionar infraestrutura base na Azure** (`ADMIN_CIDR` restrito é obrigatório; revise em `--dry-run` antes de aplicar):
   ```bash
   ADMIN_CIDR="$(curl -fsS https://ifconfig.me)/32" bash infra/azure/provision_azure_cli.sh --dry-run
   ADMIN_CIDR="$(curl -fsS https://ifconfig.me)/32" bash infra/azure/provision_azure_cli.sh --apply
   ```
2. **Na VM Azure (`brazilsouth`), preparar o ambiente:**
   - Instalar Docker Engine + Docker Compose plugin e clonar o repositório em `AZURE_DEPLOY_PATH` (ex.: `/opt/berkanan/Challenge2_berkanan`).
   - Copiar e preencher os segredos reais:
     ```bash
     cp infra/azure/.env.prod.example infra/azure/.env.prod
     # Editar POSTGRES_PASSWORD, GEMINI_API_KEY, API_DOMAIN e CORS_ALLOWED_ORIGIN
     ```
3. **Executar o bootstrap idempotente:**
   ```bash
   bash infra/azure/bootstrap_stack.sh
   ```
   O script:
   - Valida que não há senhas padrão (`CHANGE_ME_*` / `dev_only_change_me`);
   - Sobe `postgres` e `chromadb`;
   - Executa `migrations/migrate.sh` com `SEED=0` (aplicando qualquer migração nova mesmo em volume existente);
   - Verifica se a coleção `${CHROMA_COLLECTION}` possui chunks e, se necessário (ou se `FORCE_REINDEX=1`), executa `scripts/ingest_chroma.py`;
   - Sobe `backend` e `caddy` e valida `GET /health`.
4. **Deploy contínuo controlado e rollback (`.github/workflows/deploy-azure.yml`):**
   - Configure no GitHub Environment `azure-staging` os secrets `AZURE_VM_HOST`, `AZURE_VM_USER`, `AZURE_VM_SSH_KEY` e `AZURE_DEPLOY_PATH`.
   - Dispare manualmente em *Actions → Deploy Azure Staging* (`workflow_dispatch`). Em caso de falha no bootstrap, o workflow reverte automaticamente para o commit Git anterior (`PREV_SHA`) e reexecuta `bootstrap_stack.sh`.

---

## 3. Boas Práticas Aplicadas no `backend/Dockerfile`

1. **Imagem explícita e enxuta:** `python:3.12.7-slim-bookworm`.
2. **Execução sem privilégios de root:** processo Uvicorn sob o usuário dedicado `appuser` (`UID 10001`, `GID 10001`).
3. **Preservação do contrato de inicialização:** `uvicorn main:api --host 0.0.0.0 --port 8000`.
4. **Healthcheck nativo:** verifica `http://127.0.0.1:8000/openapi.json` via `urllib.request`.
5. **Nota de otimização R6/R7 (em coordenação com PR #40):** quando as dependências de OCR/embeddings entrarem na `main`, manter wheel CPU-only para evitar pacotes CUDA desnecessários na imagem de produção.

---

## 4. Requisitos Mobile First, Privacidade e Testes em 4G

- **HTTPS obrigatório:** `navigator.mediaDevices.getUserMedia()` exige origem segura (`https://`) fora de `localhost`.
- **Compressão no cliente (ADR-002):** ~1280 px no maior lado, JPEG, até ~300 KB (`MAX_UPLOAD_BYTES=307200` no backend e `CADDY_MAX_BODY_SIZE=512KB` no proxy).
- **Privacidade e LGPD (ADR-008):** nunca registrar `image_base64` nem associar `user_profile` a identificadores pessoais nos logs do Docker/Caddy ou na tabela `metricas_requisicao`.
- **Roteiro de validação 4G:** validar upload de 150–300 KB sob perfil *Fast 4G* / *Regular 4G* e conferir na view `vw_checagem_limiares_monitoramento` se a latência mediana permanece **≤ 10 s**.
