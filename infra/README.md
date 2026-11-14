# Infraestrutura e Operação — Challenge 2 Berkanan (R6)

Este diretório concentra utilitários operacionais e configurações de suporte para os serviços de infraestrutura do projeto, sob responsabilidade de **Caio Soares de Andrade (R6 — Engenheiro DevOps)**.

## 1. Visão Geral dos Artefatos de Infraestrutura

- **Container do Backend:** [backend/Dockerfile](../backend/Dockerfile)
- **Orquestração Local / Deploy:** [compose.yaml](../compose.yaml)
- **Variáveis de Ambiente:** [.env.example](../.env.example)
- **Documentação Arquitetural de Deploy:** [docs/architecture/DEPLOYMENT.md](../docs/architecture/DEPLOYMENT.md)
- **Scripts de Verificação e Smoke Test:**
  - [scripts/verify_baseline.py](../scripts/verify_baseline.py)
  - [scripts/smoke_backend.sh](../scripts/smoke_backend.sh)
  - [infra/scripts/check_compose.sh](scripts/check_compose.sh)

## 2. Integração Pendente com Banco de Dados (Handoff R4 → R6)

Conforme registrado em [docs/context/INDEX.md](../docs/context/INDEX.md):
- O serviço `postgres` (PostgreSQL 16) e o serviço `chromadb` estão provisionados em `compose.yaml` com volumes persistentes e healthchecks.
- As migrações SQL (`001_fontes.sql` a `004_metricas.sql` e `migrate.sh`, desenvolvidas por **Davi — R4**) serão conectadas ao fluxo de inicialização assim que forem adicionadas ao repositório.
- **Prometheus não deve ser adicionado** (decisão aprovada no ADR-008). O monitoramento utiliza logs e a tabela `metricas_requisicao` no próprio PostgreSQL.
