# MLOps — Versionamento, Rastreabilidade e Monitoramento (R7)

> **Responsável:** Caio Soares de Andrade (**R7 — Engenheiro de ML/MLOps**)  
> **Referência conceitual:** Kreuzberger, Kühl e Hirschl (*IEEE Access*, 2023) adaptado para aplicações baseadas em LLMs e RAG (ADR-006 e ADR-008).

---

## 1. Adaptação de MLOps para o Contexto do Berkanan

O **Challenge 2 Berkanan** utiliza modelos de linguagem e de visão computacional existentes e **não realiza treinamento ou ajuste fino (fine-tuning) de modelos próprios** nesta fase. Por isso, a arquitetura MLOps foi desenhada para ser leve, reprodutível e sem serviços supérfluos:

| Componente MLOps (Referência) | Decisão no Projeto Berkanan | Localização / Implementação |
|---|---|---|
| **C1 — CI/CD** | **Alta prioridade (`APROVADO` — ADR-007):** GitHub Actions validando baseline, sintaxe, smoke tests e build Docker | [.github/workflows/ci.yml](../.github/workflows/ci.yml) |
| **C2 — Repositório de Código** | **Alta prioridade (`APROVADO`):** Git/GitHub centralizando código, snapshots, prompts, manifestos e ADRs | Raiz do repositório |
| **C3 — Orquestração de Workflow** | **Aplicado (`APROVADO` — ADR-004):** LangGraph coordenando os agentes com roteamento determinístico por regras | [backend/graph.py](../backend/graph.py) |
| **C4 — Feature Store** | **Não implementada como serviço separado (`APROVADO`):** PostgreSQL (dados estruturados) + ChromaDB (vetores) suprem o armazenamento | [compose.yaml](../compose.yaml) (ADR-001) |
| **C5 — Infraestrutura de Treino** | **Não necessária (`APROVADO`):** Não há treinamento de modelos; inferência e OCR rodam em CPU via Docker Compose | [compose.yaml](../compose.yaml) |
| **C6 — Model Registry (Adaptado)** | **Adaptado (`PROPOSTO` — ADR-006):** Controle de versões de modelos externos, prompts, parâmetros de inferência e índices (`base_conhecimento_v1`...) | [mlops/manifests/runtime-manifest.yaml](manifests/runtime-manifest.yaml) e [mlops/prompts/](prompts) |
| **C7 — Metadata Store** | **Aplicado (`PROPOSTO` — ADR-006):** Registro de linhagem e resultados dos benchmarks (RAG vs LLM, Verificador A/B/C, OCR) | [mlops/experiments/](experiments) e PostgreSQL |
| **C8 — Model Serving** | **Alta prioridade (`APROVADO` — ADR-003):** FastAPI (`main:api`) expondo o fluxo de inferência e análise | [backend/main.py](../backend/main.py) |
| **C9 — Monitoramento** | **Alta prioridade (`APROVADO` — ADR-008):** Logs + tabela `metricas_requisicao` no PostgreSQL (sem Prometheus; Grafana opcional na semana 5) | [mlops/monitoring/](monitoring) |

---

## 2. Organização deste Diretório

- [manifests/runtime-manifest.yaml](manifests/runtime-manifest.yaml): Manifesto canônico de configuração de execução (modelos, provedor, versão de prompt, versão do índice ChromaDB, OCR, verificador e commit Git). Campos ainda não definidos ou não integrados no código estão explicitamente marcados como `not_configured`.
- [prompts/README.md](prompts/README.md): Convenção de versionamento e template de metadados para os prompts dos agentes.
- [experiments/README.md](experiments/README.md): Regras de versionamento dos índices vetoriais (`base_conhecimento_v1`, `v2`...) e diretrizes de rastreabilidade para os benchmarks de R3.
- [monitoring/README.md](monitoring/README.md): Arquitetura de observabilidade baseada em PostgreSQL, limiares de qualidade e roteamento de feedback entre R2, R3, R4, R5 e R6/R7.
