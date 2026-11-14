# CLAUDE.md — Ponto de Entrada Rápido (Challenge 2 Berkanan)

Este arquivo orienta o Claude Code e demais assistentes de IA no repositório do **Challenge 2 Berkanan** (UnB — *Tópicos Especiais em Engenharia de Software: Sistemas de Machine Learning*, 2026/02).

A governança deste repositório é **global e compartilhada por toda a equipe (papéis R1 a R7)**. Quando um integrante solicitar uma tarefa, identifique o papel correspondente (Arquitetura/Orquestração R1/R2, Ciência de Dados/Benchmarks R3, Engenharia de Dados/OCR R4, Backend/Frontend R5 ou DevOps/MLOps R6/R7) e siga as regras canônicas abaixo.

---

## 1. Documentos Canônicos (Leia Primeiro)

Toda a documentação normativa e de contexto está centralizada nos seguintes arquivos:

- **Governança global para agentes e colaboradores:** [AGENTS.md](AGENTS.md) e [docs/context/AGENTS.md](docs/context/AGENTS.md)
- **Índice consolidado do projeto (escopo, arquitetura, métricas e pendências):** [docs/context/INDEX.md](docs/context/INDEX.md)
- **Manifesto de documentos e ADRs (SHA-256 e status):** [docs/context/MANIFEST.yaml](docs/context/MANIFEST.yaml)
- **Fontes originais preservadas (imutáveis):**
  - [docs/context/sources/contextoCLAUDEV2.md](docs/context/sources/contextoCLAUDEV2.md)
  - [docs/context/sources/adr.pdf](docs/context/sources/adr.pdf) (ADR-001 a ADR-008)
  - [docs/context/sources/5_perguntas_escopo_essential_question.pdf](docs/context/sources/5_perguntas_escopo_essential_question.pdf)
- **Matriz de responsabilidades e handoff (R1–R7):** [docs/handoff/RESPONSIBILITIES.md](docs/handoff/RESPONSIBILITIES.md)
- **Baseline inicial do Backend (`backend-whatsapp-v0.1.0`):** [docs/baselines/backend-whatsapp-v0.1.0.md](docs/baselines/backend-whatsapp-v0.1.0.md)
- **Manifesto de configuração e versões MLOps:** [mlops/manifests/runtime-manifest.yaml](mlops/manifests/runtime-manifest.yaml)

> **Contextos pessoais (`.local/`):** Anotações ou instruções particulares de um colaborador ficam em `.local/` (ignorado pelo Git) e só devem ser usadas quando indicadas explicitamente na conversa.

---

## 2. Mapa Rápido por Papel (R1 a R7)

- **R1 / R2 (João Victor — Negócio, Arquitetura e Orquestração):** evolução de ADRs, coordenador determinístico por regras (`backend/graph.py`), agente de comparação e verificador por regras (Config. B).
- **R3 (Gustavo — Líder, Ciência de Dados e Benchmarks):** conjunto de teste (~50 perguntas e ~30 fotos), revisão de gabaritos nas fontes oficiais e execução dos benchmarks (RAG vs LLM, Verificador A/B/C, OCR) em `mlops/experiments/`.
- **R4 (Davi Rodrigues — Engenharia de Dados e Regras OCR):** conferência das 5 fontes oficiais, migrações e carga do PostgreSQL (TACO, limites IN 75, `produtos_lidos`, `metricas_requisicao`), ingestão no ChromaDB (`base_conhecimento_v1`) e regras de extração/validação do OCR.
- **R5 (Carlos — Engenharia de Software Backend e Frontend):** endpoints FastAPI (`backend/main.py`), agente nutricional com RAG/PostgreSQL, verificador com LLM (Config. C), integração do OCR na API e app web Mobile First (React + Vite + Tailwind) em `frontend/`.
- **R6 / R7 (Caio Soares de Andrade — DevOps e MLOps):** estrutura do repositório, Docker/Docker Compose (`compose.yaml`), CI/CD (`.github/workflows/ci.yml`), versionamento de modelos/prompts/índices (`mlops/`) e infraestrutura de monitoramento.

---

## 3. Comandos Úteis de Verificação e Execução

```bash
# 1. Verificar integridade SHA-256 do snapshot original e das fontes documentais
python3 scripts/verify_baseline.py

# 2. Validar sintaxe Python do backend
python3 -m py_compile backend/*.py scripts/verify_baseline.py

# 3. Executar a API FastAPI localmente (dentro de backend/)
cd backend && uvicorn main:api --reload --host 0.0.0.0 --port 8000

# 4. Executar smoke tests automatizados da API (enable_verifier=true e false)
bash scripts/smoke_backend.sh

# 5. Validar e subir infraestrutura Docker Compose
bash infra/scripts/check_compose.sh
docker compose up --build -d
```

---

## 4. Regras Críticas do Projeto

1. **Localização canônica:** O código ativo do backend fica em [backend/](backend) (`uvicorn main:api`). O diretório [snapshots/backend/whatsapp-v0.1.0/original/](snapshots/backend/whatsapp-v0.1.0/original) é registro histórico imutável — **nunca edite**.
2. **Transparência de status:** Diferencie sempre `APROVADO`, `PENDENTE`, `PROPOSTO`, `IMPLEMENTADO` e `SIMULADO`. Não declare integrações com PostgreSQL, ChromaDB ou OCR como concluídas enquanto o código estiver em modo mock.
3. **Regras de negócio e segurança (APROVADAS):**
   - Zero cálculo numérico pelo LLM (todo número nutricional vem do PostgreSQL ou do rótulo confirmado via código determinístico);
   - Citação obrigatória de fontes recuperadas pelo RAG (sem evidência → responder `"não há evidência suficiente"`);
   - Coordenador roteia por regras sem chamar o LLM (máximo de 1 a 2 chamadas ao LLM por resposta);
   - Confirmação obrigatória pelo usuário para todos os dados lidos via OCR;
   - Nunca afirmar que um produto é "livre de alergênicos" (sempre exigir conferência na embalagem);
   - Monitoramento via logs + tabela `metricas_requisicao` no PostgreSQL (**não utilizar Prometheus**).
