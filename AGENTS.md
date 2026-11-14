# AGENTS.md — Guia Global de Governança para Agentes e Colaboradores (Challenge 2 Berkanan)

Este repositório pertence à **Equipe Berkanan** (UnB — *Tópicos Especiais em Engenharia de Software: Sistemas de Machine Learning*, 2026/02).

Este é o ponto de entrada global do projeto, compartilhado por **todos os integrantes e papéis (R1 a R7)**. Qualquer agente de IA (Claude Code, Antigravity, Codex, Copilot, Cursor, etc.) ou colaborador que atue neste repositório **DEVE** seguir estas diretrizes antes de modificar código, dados, experimentos, infraestrutura ou documentação.

> **Nota sobre contextos individuais:** Personas, rascunhos ou planos particulares de cada integrante pertencem ao diretório `.local/` (ignorado pelo Git) e só devem ser carregados quando explicitamente solicitados na sessão. Documentos versionados devem manter escopo global para toda a equipe.

---

## 1. Leitura Obrigatória Antes de Qualquer Alteração

Antes de propor ou implementar mudanças, consulte os documentos canônicos nesta ordem:

1. **Orientação global de contexto:** [docs/context/AGENTS.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/AGENTS.md)
2. **Índice consolidado do projeto:** [docs/context/INDEX.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/INDEX.md)
3. **Manifesto de documentos e ADRs:** [docs/context/MANIFEST.yaml](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/MANIFEST.yaml)
4. **Fontes documentais originais (imutáveis):**
   - [docs/context/sources/contextoCLAUDEV2.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/sources/contextoCLAUDEV2.md)
   - [docs/context/sources/adr.pdf](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/sources/adr.pdf) (ADR-001 a ADR-008)
   - [docs/context/sources/5_perguntas_escopo_essential_question.pdf](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/sources/5_perguntas_escopo_essential_question.pdf)
5. **Matriz de responsabilidades e handoff (R1–R7):** [docs/handoff/RESPONSIBILITIES.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/handoff/RESPONSIBILITIES.md)
6. **Baseline do backend e manifesto MLOps:** [docs/baselines/backend-whatsapp-v0.1.0.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/baselines/backend-whatsapp-v0.1.0.md) e [mlops/manifests/runtime-manifest.yaml](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/mlops/manifests/runtime-manifest.yaml)

---

## 2. Preservação das Decisões Arquiteturais (ADRs)

Não contradiga nem substitua decisões marcadas como **APROVADO** sem validação do líder (**Gustavo — R3**) e do arquiteto (**João Victor — R2**). Os status formais constam em `docs/context/MANIFEST.yaml` e em `docs/context/sources/adr.pdf`:

- **ADR-001 (`APROVADO` — Armazenamento híbrido):** PostgreSQL para dados estruturados (TACO, limites da IN 75/2020, cache de produtos lidos e métricas) + ChromaDB para textos de fontes oficiais (RAG).
- **ADR-002 (`APROVADO PARCIALMENTE` — Extração de rótulos):** Compressão da foto no navegador mobile (~1280 px, JPEG, ≤ 300 KB) → OpenCV no servidor → OCR tradicional em CPU (Tesseract ou PaddleOCR, escolha pendente de benchmark na Semana 4) → Regras determinísticas e validação de consistência → **Confirmação obrigatória pelo usuário** (LLM multimodal apenas como reserva).
- **ADR-003 (`APROVADO` — Backend central):** FastAPI no servidor centralizando a orquestração; nenhum processamento pesado roda no celular.
- **ADR-004 (`APROVADO` — Orquestração):** LangGraph com **coordenador determinístico baseado em regras** (sem chamada ao LLM para roteamento) e limite máximo de **1 a 2 chamadas ao LLM por resposta**.
- **ADR-005 (`EM AVALIAÇÃO` / Critério `APROVADO` — Verificação):** Três configurações em benchmark (A: sem verificador; B: regras determinísticas em código; C: verificador com LLM). A Configuração C só é adotada se obtiver **≥ +5 pontos percentuais de fidelidade** sobre B com **≤ +3 segundos de latência adicional**. O verificador deve ser configurável (`enable_verifier`).
- **ADR-006 (`PROPOSTO PARA VALIDAÇÃO` — Versionamento MLOps):** Controle de versões de modelos externos, prompts, configurações de inferência e índices vetoriais (`base_conhecimento_v1`, `v2`...) via Git e manifestos estruturados.
- **ADR-007 (`APROVADO` — CI/CD):** GitHub Actions validando sintaxe, dependências, containers e smoke tests a cada push/PR.
- **ADR-008 (`APROVADO` — Monitoramento):** Logs + tabela `metricas_requisicao` no PostgreSQL (uma linha por requisição). **Não utilizar Prometheus.** Grafana é opcional apenas na semana 5.

---

## 3. Regras Inegociáveis de Segurança, Domínio e Escopo

1. **Zero cálculo ou invenção numérica pelo LLM:** Todo valor nutricional vem do PostgreSQL ou do rótulo confirmado pelo usuário, processado via SQL/código determinístico. O LLM apenas explica.
2. **Citação obrigatória de evidências:** Toda resposta deve citar a fonte oficial recuperada via RAG. Quando não houver cobertura na base ou no rótulo, responder explicitamente: `"não há evidência suficiente"`.
3. **Alergênicos:** Ler a seção `"ALÉRGICOS"` do rótulo, mas **nunca afirmar que um produto é "livre de alergênicos"**. Exibir sempre aviso para o usuário conferir a embalagem física.
4. **Aviso médico/nutricional fixo:** O sistema possui caráter informativo e não realiza diagnóstico, prescrição de dieta, recomendação de doses de medicamentos ou planos alimentares individualizados.
5. **Privacidade e LGPD:** Não armazenar fotografias de rótulos nem perfis pessoais de saúde em bancos de dados ou arquivos de log sem consentimento explícito.
6. **Foco no escopo aprovado:** Não implementar apps nativos Android/iOS, PWA, OCR no cliente, leitura de código de barras / Open Food Facts ou detecção de símbolo de transgênicos sem deliberação da equipe.

---

## 4. Atuação Coordenada pelos Papéis da Equipe (R1 a R7)

O agente deve identificar qual papel ou entrega está sendo trabalhado na tarefa solicitada pelo usuário e respeitar as interfaces com os demais integrantes:

| Papel | Responsável | Escopo de Atuação no Repositório |
|---|---|---|
| **R1 Stakeholder + R2 Arquiteto** | **João Victor** | Escopo, Essential Question, ADRs (`docs/context/`), coordenador determinístico por regras no LangGraph, agente de comparação e verificação por regras (Config. B) em `backend/` |
| **R3 Cientista de Dados (Líder)** | **Gustavo** | Conjunto de teste (~50 perguntas e ~30 fotos), gabarito conferido nas fontes, execução dos benchmarks (RAG vs LLM, Verificador A/B/C, OCR), avaliação com usuários e métricas em `mlops/experiments/` |
| **R4 Engenheiro de Dados** | **Davi Rodrigues** | Fontes oficiais, migrações e carga do PostgreSQL (`001_fontes.sql` a `004_metricas.sql`, TACO, limites IN 75, cache, `metricas_requisicao`), ingestão no ChromaDB (`base_conhecimento_v1`) e regras de extração/validação do OCR |
| **R5 Engenheiro de Software** | **Carlos** | Evolução da API FastAPI (`backend/main.py`), agente nutricional conectado ao RAG/PostgreSQL, verificador com LLM (Config. C), integração do OCR à API e aplicação web Mobile First em `frontend/` |
| **R6 DevOps + R7 MLOps** | **Caio Soares de Andrade** | Estrutura do repositório, preservação de baselines (`snapshots/`), Docker/Docker Compose, CI/CD (`.github/workflows/`), versionamento de modelos/prompts/índices (`mlops/`) e infraestrutura de monitoramento |

- Ao alterar contratos compartilhados (`backend/schemas.py`, `backend/state.py`, variáveis de ambiente, esquema SQL ou metadados do ChromaDB), verifique o impacto nos demais papéis em [docs/handoff/RESPONSIBILITIES.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/handoff/RESPONSIBILITIES.md).

---

## 5. Rigor Técnico, Testes e Proibições Gerais

- **Classifique o estado real de cada item com precisão:**
  - `APROVADO`: decisão formalmente validada pela equipe.
  - `APROVADO PARCIALMENTE` / `EM AVALIAÇÃO`: decisão com diretriz definida, mas dependente de benchmark empírico.
  - `PROPOSTO`: sugestão técnica que aguarda validação.
  - `PENDENTE`: etapa ou entrega ainda não concluída.
  - `IMPLEMENTADO`: funcionalidade existente e verificada em código executável.
  - `SIMULADO`: código esqueleto/mock (como os dados fixos iniciais em `backend/graph.py`).
- **Preservação de arquivos históricos e migrações:**
  - Nunca edite ou remova os arquivos em `snapshots/backend/whatsapp-v0.1.0/` ou em `docs/context/sources/`.
  - Quando as migrações numeradas do PostgreSQL (`001_*.sql`...) estiverem no repositório, nunca edite uma migração já aplicada; crie uma nova migração sequencial.
- **Proibição de dados ou resultados inventados:** Nunca invente resultados de benchmark, métricas de acurácia/latência, versões de modelos não testadas ou valores normativos da ANVISA/TACO de memória.
- **Infraestrutura enxuta:** Não adicione serviços fora da arquitetura aprovada (como Prometheus, Redis, filas pesadas) sem revisão de R2 e aprovação do líder (R3).
- **Verificação e commits:**
  - Valide alterações executando `python3 scripts/verify_baseline.py`, `bash scripts/smoke_backend.sh` e `bash infra/scripts/check_compose.sh` conforme aplicável.
  - Realize commits pequenos, atômicos e com mensagens claras (a avaliação individual da disciplina considera a qualidade e relevância dos commits de cada integrante).
