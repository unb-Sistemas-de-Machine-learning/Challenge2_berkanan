# Divisão de Responsabilidades e Interfaces de Handoff (R1 a R7)

Este documento descreve as responsabilidades de cada papel da **Equipe Berkanan** segundo o modelo de referência de MLOps adotado na disciplina (Kreuzberger, Kühl e Hirschl, *IEEE Access*, 2023) e define os contratos de integração (handoff) entre todas as frentes do projeto.

---

## 1. Matriz Global de Papéis (`APROVADO` em 11/11/2026)

| Papel | Integrante | Escopo de Atuação | Diretórios Principais no Repositório |
|---|---|---|---|
| **R1 — Stakeholder** | João Victor | Definição do problema de negócio, Essential Question, escopo positivo/negativo e requisitos do usuário | `docs/context/` |
| **R2 — Arquiteto** | João Victor | Decisões arquiteturais (ADR-001 a ADR-008), coordenador determinístico por regras no LangGraph, agente de comparação e verificador por regras (Config. B) | `docs/context/sources/adr.pdf`, `backend/graph.py`, `backend/state.py` |
| **R3 — Cientista de Dados (Líder)** | Gustavo | Conjunto de teste (~50 perguntas e ~30 fotos de rótulos), gabarito conferido nas fontes, condução dos benchmarks (RAG vs LLM, Verificador A/B/C, OCR), avaliação com usuários e métricas | `mlops/experiments/` |
| **R4 — Engenheiro de Dados** | Davi Rodrigues | Coleta e conferência das 5 fontes oficiais, migrações e seeds do PostgreSQL (`001_fontes.sql` a `004_metricas.sql`, TACO, limites IN 75, `produtos_lidos`, `metricas_requisicao`), ingestão no ChromaDB (`base_conhecimento_v1`), regras de extração/validação do OCR | `infra/` (migrações SQL), `backend/` (módulos de dados/OCR) |
| **R5 — Engenheiro de Software** | Carlos | API FastAPI (`main:api`), agente nutricional conectado ao RAG/PostgreSQL, agente verificador com LLM (Config. C), integração do pipeline OpenCV/OCR na API e desenvolvimento do frontend web Mobile First (React + Vite + Tailwind) | `backend/`, `frontend/` |
| **R6 — Engenheiro DevOps** | Caio Soares de Andrade | Arquitetura de diretórios do repositório, preservação de baselines, `backend/Dockerfile`, `compose.yaml`, variáveis de ambiente (`.env.example`), CI/CD (`.github/workflows/ci.yml`), smoke tests e deploy | `.github/workflows/`, `backend/Dockerfile`, `compose.yaml`, `infra/`, `scripts/`, `snapshots/` |
| **R7 — Engenheiro MLOps** | Caio Soares de Andrade | Manifesto de runtime (`mlops/manifests/runtime-manifest.yaml`), convenções de versionamento de modelos, prompts (`mlops/prompts/`) e índices vetoriais (`base_conhecimento_vN`), rastreabilidade de experimentos e estrutura de monitoramento no PostgreSQL (`mlops/monitoring/`) | `mlops/`, `docs/baselines/` |

---

## 2. Interfaces de Handoff entre os Papéis

### 2.1 R1 / R2 (João Victor) ↔ Demais Papéis
- **Entrega para a equipe:** ADRs aprovados (`docs/context/sources/adr.pdf`), coordenador determinístico por regras (`coordinator_node`), agente de comparação e verificador por regras (Configuração B) em `backend/graph.py`.
- **Recebe de R4 e R5:** Esquema de dados consultáveis no PostgreSQL (TACO e limites da IN 75) e integração com o estado `AgentState` (`backend/state.py`) e contratos da API (`backend/schemas.py`).
- **Handoff para R3:** Disponibiliza o fluxo com as Configurações A e B prontas para medição comparativa no benchmark do verificador.

### 2.2 R4 (Davi Rodrigues) ↔ R2, R3, R5 e R6/R7
- **Entrega para R2 e R5:**
  - Tabelas `fontes_documentos`, `taco_alimentos`, `limites_rotulagem` e `produtos_lidos` populadas no PostgreSQL;
  - Coleção vetorial `base_conhecimento_v1` indexada no ChromaDB com metadados obrigatórios (`documento`, `fonte_id`, `arquivo`, `pagina`, `versao_indice`);
  - Funções/expressões regulares de extração e validação de consistência dos campos nutricionais e da seção `"ALÉRGICOS"`.
- **Entrega para R6/R7:**
  - Arquivos `migrations/001_fontes.sql` a `004_metricas.sql`, `migrations/migrate.sh` e `seeds/seed_exemplo.sql` para automação no `compose.yaml` e alinhamento das colunas de `metricas_requisicao` (ADR-008);
  - Atualização da versão do índice e modelo de embeddings em `mlops/manifests/runtime-manifest.yaml`.
- **Entrega para R3:** Limites literais da IN 75/2020 e fontes conferidas para validação cruzada do gabarito de testes.

### 2.3 R5 (Carlos) ↔ R2, R3, R4 e R6/R7
- **Entrega para R2 e R3:**
  - Endpoint `POST /api/analyze` e rotas auxiliares integradas ao PostgreSQL, ChromaDB e pipeline OpenCV/OCR;
  - Agente nutricional real e verificador com LLM (Configuração C) acionável via `enable_verifier`;
  - Prompts dos agentes registrados em `mlops/prompts/`.
- **Entrega para usuários e R3 (Semana 5/6):** Aplicação web Mobile First em `frontend/` (React + Vite + Tailwind) com compressão de imagem no navegador (~1280 px, JPEG, ≤ 300 KB) e tela de confirmação obrigatória dos valores extraídos pelo OCR.
- **Coordenação com R6:** Atualização de `backend/requirements.txt` (para rebuild automático no `backend/Dockerfile` e CI) e entrega do `frontend/` para inclusão no `compose.yaml`.

### 2.4 R3 (Gustavo — Líder) ↔ Todos os Papéis
- **Entrega para a equipe:** Conjunto de teste revisado (~50 perguntas nas categorias A–G e ~30 fotos de rótulos com gabarito conferido nas fontes) e consolidação dos relatórios de benchmark em `mlops/experiments/`.
- **Decisões baseadas em evidência:**
  - Define, a partir do benchmark da Semana 3, se o sistema adota a **Configuração B (regras)** ou **Configuração C (LLM)** para o verificador (critério: ≥ +5 pontos percentuais de fidelidade e ≤ +3 s de latência adicional);
  - Define, a partir do benchmark da Semana 4, qual motor de OCR (**Tesseract** vs **PaddleOCR**) será fixado no container de produção.

### 2.5 R6 / R7 (Caio Soares de Andrade) ↔ Todos os Papéis
- **Entrega para a equipe:**
  - Estrutura canônica do repositório, preservação imutável de snapshots (`snapshots/backend/whatsapp-v0.1.0/`) e scripts de verificação (`scripts/verify_baseline.py`, `scripts/smoke_backend.sh`);
  - Ambiente reproduzível em Docker Compose (`compose.yaml` com `backend`, `postgres` e `chromadb`) e pipeline CI no GitHub Actions (`.github/workflows/ci.yml`);
  - Estrutura de versionamento MLOps (`mlops/manifests/runtime-manifest.yaml`, `mlops/prompts/`, `mlops/experiments/`) e diretrizes de monitoramento via PostgreSQL (`mlops/monitoring/`).
- **Roteamento de feedback operacional (ADR-008):**
  - Falhas de leitura/extração → **R4 (Davi)**;
  - Queda de fidelidade/recall → **R3 (Gustavo)**;
  - Latência, containers e infraestrutura → **R6/R7 (Caio)**;
  - Bugs de API, integração de agentes e UI → **R5 (Carlos)**;
  - Mudanças estruturais ou de tecnologia → **R2 (João Victor)**.
