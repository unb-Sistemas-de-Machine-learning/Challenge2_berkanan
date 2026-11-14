# Divisão de Responsabilidades e Handoff (R1 a R7)

Este documento descreve as fronteiras de responsabilidade da **Equipe Berkanan** segundo o modelo de referência de MLOps adotado na disciplina (Kreuzberger, Kühl e Hirschl, *IEEE Access*, 2023) e orienta o handoff entre a infraestrutura inicial (R6/R7) e os demais integrantes.

---

## 1. Matriz de Papéis da Equipe (`APROVADO` em 11/11/2026)

| Papel | Integrante | Escopo de Atuação | Diretórios Principais no Repositório |
|---|---|---|---|
| **R1 — Stakeholder** | João Victor | Definição do problema de negócio, Essential Question, escopo positivo/negativo e requisitos do usuário | `docs/context/` |
| **R2 — Arquiteto** | João Victor | Decisões arquiteturais (ADR-001 a ADR-008), coordenador determinístico por regras no LangGraph, agente de comparação e verificador por regras (Config. B) | `docs/context/sources/adr.pdf`, `backend/graph.py`, `backend/state.py` |
| **R3 — Cientista de Dados (Líder)** | Gustavo | Conjunto de teste (~50 perguntas e ~30 fotos de rótulos), gabarito conferido nas fontes, condução dos benchmarks (RAG vs LLM, Verificador A/B/C, OCR), avaliação com usuários e métricas | `mlops/experiments/` |
| **R4 — Engenheiro de Dados** | Davi Rodrigues | Coleta e conferência das 5 fontes oficiais, migrações e seeds do PostgreSQL (`001_fontes.sql` a `004_metricas.sql`, TACO, limites IN 75, `produtos_lidos`, `metricas_requisicao`), ingestão no ChromaDB (`base_conhecimento_v1`), regras de extração/validação do OCR | `infra/` (migrações SQL futuras), `backend/` (módulos de dados/OCR) |
| **R5 — Engenheiro de Software** | Carlos | API FastAPI (`main:api`), agente nutricional conectado ao RAG/PostgreSQL, agente verificador com LLM (Config. C), integração do pipeline OpenCV/OCR na API e desenvolvimento do frontend web Mobile First (React + Vite + Tailwind) | `backend/`, `frontend/` |
| **R6 — Engenheiro DevOps** | Caio Soares de Andrade | Arquitetura de diretórios do repositório, preservação de baselines, `backend/Dockerfile`, `compose.yaml`, variáveis de ambiente (`.env.example`), CI/CD (`.github/workflows/ci.yml`), smoke tests e deploy | `.github/workflows/`, `backend/Dockerfile`, `compose.yaml`, `infra/`, `scripts/`, `snapshots/` |
| **R7 — Engenheiro MLOps** | Caio Soares de Andrade | Manifesto de runtime (`mlops/manifests/runtime-manifest.yaml`), convenções de versionamento de modelos, prompts (`mlops/prompts/`) e índices vetoriais (`base_conhecimento_vN`), rastreabilidade de experimentos e estrutura de monitoramento no PostgreSQL (`mlops/monitoring/`) | `mlops/`, `docs/baselines/` |

---

## 2. O que foi entregue por R6/R7 nesta etapa (14/11/2026)

1. **Auditoria e Preservação do Baseline (`backend-whatsapp-v0.1.0`):**
   - Snapshot imutável dos 7 arquivos originais recebidos via WhatsApp em `snapshots/backend/whatsapp-v0.1.0/original/`.
   - Hashes criptográficos em `snapshots/backend/whatsapp-v0.1.0/SHA256SUMS` e metadados completos em `snapshots/backend/whatsapp-v0.1.0/manifest.yaml`.
   - Verificador automatizado em `scripts/verify_baseline.py`.
2. **Preservação Documental e Governança:**
   - Fontes originais preservadas em `docs/context/sources/` (`contextoCLAUDEV2.md`, `adr.pdf`, `5_perguntas_escopo_essential_question.pdf`).
   - Índice consolidado em `docs/context/INDEX.md` e manifesto de integridade em `docs/context/MANIFEST.yaml`.
   - Instruções para agentes em `AGENTS.md` e `CLAUDE.md`.
3. **Containerização e Orquestração Local:**
   - `backend/Dockerfile` leve (Python 3.12-slim, usuário não-root, Uvicorn em `main:api`).
   - `compose.yaml` com serviços `backend`, `postgres` (PostgreSQL 16) e `chromadb`, rede isolada, volumes nomeados e healthchecks verificáveis.
   - `.env.example` documentado sem segredos reais.
4. **Integração Contínua (CI):**
   - Workflow `.github/workflows/ci.yml` com permissões mínimas, verificação de integridade do baseline, compilação sintática, execução de `scripts/smoke_backend.sh`, build Docker e validação do Docker Compose.
5. **Estrutura Inicial MLOps:**
   - Manifesto de execução em `mlops/manifests/runtime-manifest.yaml`.
   - Estrutura e convenções de versionamento em `mlops/prompts/`, `mlops/experiments/` e `mlops/monitoring/`.

---

## 3. Pontos de Handoff para os Demais Integrantes

### Para R4 (Davi Rodrigues — Engenharia de Dados)
- Assim que os arquivos `migrations/001_fontes.sql` a `004_metricas.sql`, `migrations/migrate.sh` e `seeds/seed_exemplo.sql` forem adicionados ao repositório, coordene com **Caio (R6/R7)** o mapeamento do volume no serviço `postgres` do `compose.yaml` e a validação das colunas de `metricas_requisicao` (veja [mlops/monitoring/README.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/mlops/monitoring/README.md)).
- Ao gerar a primeira coleção no ChromaDB (`base_conhecimento_v1`), atualize os metadados correspondentes em `mlops/manifests/runtime-manifest.yaml`.

### Para R2 (João Victor — Arquitetura e Orquestração) e R5 (Carlos — Backend e Frontend)
- O código executável do backend está em [backend/](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/backend). Não edite os arquivos em `snapshots/`.
- Caso novas bibliotecas Python sejam adicionadas em `backend/requirements.txt` (ex.: `psycopg`, `chromadb`, `opencv-python-headless`, `langchain-google-genai`), o `backend/Dockerfile` e o workflow `.github/workflows/ci.yml` as instalarão automaticamente.
- Quando os prompts reais dos agentes forem criados, versione-os em `mlops/prompts/` seguindo a convenção descrita em [mlops/prompts/README.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/mlops/prompts/README.md).
- Quando o código do aplicativo React + Vite + Tailwind for adicionado em [frontend/](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/frontend), acione **Caio (R6)** para habilitar o serviço `frontend` no `compose.yaml` e o job correspondente na CI.

### Para R3 (Gustavo — Ciência de Dados e Benchmarks)
- Utilize a estrutura em [mlops/experiments/](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/mlops/experiments) e o manifesto [mlops/manifests/runtime-manifest.yaml](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/mlops/manifests/runtime-manifest.yaml) para registrar o commit Git, versão do modelo, versão do prompt e versão do índice ChromaDB usados em cada rodada de benchmark (RAG vs LLM, Verificador A/B/C e OCR).
