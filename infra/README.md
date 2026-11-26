# Infraestrutura e Operação — Challenge 2 Berkanan (R6)

Este diretório concentra utilitários operacionais, scripts e configurações de deploy para os serviços de infraestrutura do projeto, sob responsabilidade de **Caio Soares de Andrade (R6 — Engenheiro DevOps)**.

## 1. Visão Geral dos Artefatos de Infraestrutura

- **Container do Backend:** [backend/Dockerfile](../backend/Dockerfile)
- **Orquestração Local (Desenvolvimento):** [compose.yaml](../compose.yaml)
- **Variáveis de Ambiente Locais:** [.env.example](../.env.example)
- **Stack de Staging/Produção na Azure (`brazilsouth`):**
  - [infra/azure/PLAYBOOK.md](azure/PLAYBOOK.md) (playbook operacional completo: ajuste de Dockerfiles por PR, orçamento de RAM, runbook, backup e troubleshooting)
  - [infra/azure/compose.prod.yaml](azure/compose.prod.yaml) (Caddy TLS + Backend + PostgreSQL + ChromaDB + `model_cache`)
  - [infra/azure/Caddyfile](azure/Caddyfile) (HTTPS automático, CORS e limite de payload `512KB`)
  - [infra/azure/.env.prod.example](azure/.env.prod.example) (template de variáveis de produção)
  - [infra/azure/bootstrap_stack.sh](azure/bootstrap_stack.sh) (subida idempotente + `migrate.sh` + `ingest_chroma.py` + healthcheck)
  - [infra/azure/provision_azure_cli.sh](azure/provision_azure_cli.sh) (provisionamento seguro com `--dry-run` padrão, NSG restrito e Static Web Apps)
  - [infra/azure/staticwebapp.config.json](azure/staticwebapp.config.json) (roteamento SPA e headers do Azure Static Web Apps)
- **Documentação Arquitetural de Deploy:** [docs/architecture/DEPLOYMENT.md](../docs/architecture/DEPLOYMENT.md) e [docs/adr/adr_009.md](../docs/adr/adr_009.md)
- **Scripts de Verificação e Smoke Test:**
  - [scripts/verify_baseline.py](../scripts/verify_baseline.py)
  - [scripts/smoke_backend.sh](../scripts/smoke_backend.sh)
  - [infra/scripts/check_compose.sh](scripts/check_compose.sh)

## 2. Integração com Banco de Dados e Feature Stores (Handoff R4 → R6)

Conforme registrado em [docs/context/INDEX.md](../docs/context/INDEX.md):
- O serviço `postgres` (PostgreSQL 16.4) e o serviço `chromadb` (0.5.20) estão provisionados em `compose.yaml` e `infra/azure/compose.prod.yaml` com volumes persistentes e healthchecks.
- As migrações SQL (`migrations/001_fontes.sql` a `011_fontes_alergenicos.sql` e `migrations/migrate.sh`, desenvolvidas por **Davi — R4**) estão integradas ao startup inicial e executam de forma idempotente no `bootstrap_stack.sh`.
- O backend conta com `backend/database.py` (PostgreSQL / TACO / limites / cache / telemetria) e `backend/chroma_client.py` (ChromaDB / RAG).
- A verificação da integração dos bancos pode ser realizada por `python3 scripts/verify_db_integration.py`.
- **Prometheus não deve ser adicionado** (decisão aprovada no ADR-008). O monitoramento utiliza logs e a tabela `metricas_requisicao` no próprio PostgreSQL.
