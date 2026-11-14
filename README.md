# Challenge 2 Berkanan — Interpretação Inteligente de Rótulos Nutricionais

Repositório oficial da Proof of Concept (PoC) acadêmica desenvolvida pela **Equipe Berkanan** na disciplina *Tópicos Especiais em Engenharia de Software: Sistemas de Machine Learning* (Universidade de Brasília — UnB, 2026/02).

---

## 1. Sobre o Projeto

- **Big Idea:** *"Empoderando pessoas com IA para compreender melhor, decidir melhor e viver melhor"* (Qualidade de Vida).
- **Essential Question:** *"Como a inteligência artificial pode usar os rótulos de produtos e fontes oficiais para ajudar a orientar os consumidores brasileiros a escolher opções mais saudáveis na sua alimentação de forma rápida e confiável?"*
- **Público-alvo:** Consumidores adultos brasileiros em situação de compra no supermercado utilizando navegador de celular (Mobile First), com atenção especial a pessoas com diabetes ou hipertensão.

---

## 2. Arquitetura e Estado Atual (Referência: 14/11/2026)

> [!IMPORTANT]
> Diferenciação rigorosa entre arquitetura aprovada e implementação atual no código:

| Componente | Tecnologia Aprovada | Status no Código |
|---|---|---|
| **Frontend Mobile First** | React + Vite + Tailwind | `PENDENTE` (diretório `frontend/` preparado para recepção) |
| **API Backend** | Python + FastAPI (`main:api`, `POST /api/analyze`) | `IMPLEMENTADO` (esqueleto funcional do baseline `whatsapp-v0.1.0`) |
| **Orquestração Multiagentes** | LangGraph (`coordinator` → `nutritional` → `verifier` opcional) | `IMPLEMENTADO` (fluxo base com respostas simuladas/mock) |
| **Extração de Rótulos** | Compressão no cliente + OpenCV + OCR (Tesseract/PaddleOCR em benchmark) + Regras + Confirmação do usuário | `PENDENTE` |
| **Banco Relacional** | PostgreSQL 16 (TACO, limites IN 75, cache, métricas) | `PROPOSTO` em `compose.yaml` (migrações R4 e integração no código `PENDENTES`) |
| **Banco Vetorial (RAG)** | ChromaDB (`base_conhecimento_v1`...) | `PROPOSTO` em `compose.yaml` (ingestão R4 e integração no código `PENDENTES`) |
| **CI/CD** | GitHub Actions | `IMPLEMENTADO` (`.github/workflows/ci.yml`) |
| **MLOps & Versionamento** | Manifestos YAML + Git + Monitoramento via PostgreSQL (sem Prometheus) | `IMPLEMENTADO` estrutura inicial em `mlops/` e `snapshots/` |

---

## 3. Estrutura do Repositório

```text
challenge_2_berkanan/
├── .github/workflows/ci.yml      # Pipeline de Integração Contínua (GitHub Actions)
├── backend/                      # Código executável canônico da API FastAPI e LangGraph
├── frontend/                     # Espaço reservado para o Web App Mobile First (React/Vite/Tailwind)
├── infra/                        # Documentação e scripts auxiliares de infraestrutura
├── mlops/                        # Manifestos de runtime, versionamento de prompts/índices, experimentos e monitoramento
├── docs/
│   ├── context/                  # Fontes originais (ADRs, contexto, 5 perguntas), INDEX.md e MANIFEST.yaml
│   ├── architecture/             # Documentação de deploy, ambientes e requisitos Mobile First
│   ├── baselines/                # Histórico e auditoria do baseline backend-whatsapp-v0.1.0
│   └── handoff/                  # Matriz de responsabilidades R1–R7 e pontos de integração
├── snapshots/                    # Preservação imutável dos arquivos originais recebidos (com SHA256SUMS)
├── scripts/                      # Scripts de verificação de integridade e smoke tests da API
├── compose.yaml                  # Orquestração Docker Compose (backend, postgres, chromadb)
├── .env.example                  # Exemplo de variáveis de ambiente (sem credenciais reais)
├── AGENTS.md                     # Diretrizes obrigatórias para agentes de IA e contribuidores
└── CLAUDE.md                     # Ponto de entrada conciso para o Claude Code
```

---

## 4. Como Executar e Validar

### 4.1 Verificar integridade do baseline e documentos de contexto

```bash
python3 scripts/verify_baseline.py
```

### 4.2 Executar o backend localmente (Python)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cd backend
uvicorn main:api --host 0.0.0.0 --port 8000
```

Em outro terminal, execute o smoke test automatizado:

```bash
bash scripts/smoke_backend.sh
```

### 4.3 Executar com Docker Compose

```bash
cp .env.example .env
docker compose up --build -d
bash scripts/smoke_backend.sh
docker compose down
```

---

## 5. Documentação Principal

- [Índice Canônico de Contexto (`docs/context/INDEX.md`)](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/INDEX.md)
- [Arquitetura de Deploy e Mobile First (`docs/architecture/DEPLOYMENT.md`)](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/architecture/DEPLOYMENT.md)
- [Auditoria do Baseline (`docs/baselines/backend-whatsapp-v0.1.0.md`)](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/baselines/backend-whatsapp-v0.1.0.md)
- [Divisão de Responsabilidades R1–R7 (`docs/handoff/RESPONSIBILITIES.md`)](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/handoff/RESPONSIBILITIES.md)
- [Guia de MLOps (`mlops/README.md`)](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/mlops/README.md)
