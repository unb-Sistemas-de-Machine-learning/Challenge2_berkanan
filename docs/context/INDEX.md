# Índice Canônico de Contexto — Challenge 2 Berkanan

**Orientações compartilhadas:** [guia global para agentes e colaboradores](AGENTS.md) e [AGENTS.md da raiz](../../AGENTS.md). Contextos pessoais são opcionais e ficam em `.local/`, fora do versionamento.

> **Data de referência documental:** 14/11/2026  
> **Disciplina:** Tópicos Especiais em Engenharia de Software: Sistemas de Machine Learning (UnB — 2026/02)  
> **Entrega final prevista:** 07/12/2026  

Este documento consolida a identidade do projeto, as decisões arquiteturais, o estado real do desenvolvimento e as pendências de todas as frentes da **Equipe Berkanan (R1 a R7)**, diferenciando rigorosamente entre o que está **APROVADO**, **PENDENTE**, **PROPOSTO**, **SIMULADO** e **IMPLEMENTADO** no código.

---

## 1. Identidade do Projeto

### 1.1 Nome e Objetivo Acadêmico e Técnico
- **Projeto:** Challenge 2 Berkanan.
- **Big Idea:** *"Empoderando pessoas com IA para compreender melhor, decidir melhor e viver melhor"* (Tema: Qualidade de Vida).
- **Challenge Statement:** Projetar e desenvolver uma solução baseada em IA que apoie a tomada de decisão em um contexto de qualidade de vida, investigando limites técnicos, realizando benchmarks reprodutíveis e documentando decisões arquiteturais (ADRs).
- **Restrições metodológicas obrigatórias da disciplina:**
  1. Entender o problema antes da solução;
  2. Justificar decisões técnicas;
  3. Explicitar riscos e limitações;
  4. Validar com métricas objetivas;
  5. Utilizar evidências confiáveis.

### 1.2 Essential Question (`APROVADO` em 12/11/2026)
> *"Como a inteligência artificial pode usar os rótulos de produtos e fontes oficiais para ajudar a orientar os consumidores brasileiros a escolher opções mais saudáveis na sua alimentação de forma rápida e confiável?"*

- **Público-alvo:** Consumidor adulto brasileiro no supermercado utilizando navegador de celular (foco especial em grupos de risco: diabetes e hipertensão).

### 1.3 Escopo (`APROVADO` em 05/11 e 12/11/2026)

**O que o sistema faz:**
- Lê a fotografia do rótulo nutricional e explica o produto: valor energético, carboidratos, açúcares totais e adicionados, proteínas, gorduras (totais, saturadas e trans), fibra alimentar, sódio, %VD e grau de processamento.
- Identifica alergênicos declarados na seção `"ALÉRGICOS"` (ex.: lactose, glúten), **sempre exigindo conferência na embalagem**.
- Compara dois produtos e indica a opção mais adequada segundo critérios oficiais, citando as fontes.
- Responde dúvidas sobre alimentação fundamentadas em documentos oficiais (Guia Alimentar, ANVISA RDC 429/2020 e IN 75/2020, OMS, SBD).
- Emite avisos específicos para usuários que informam possuir diabetes ou hipertensão.
- Responde explicitamente *"não há evidência suficiente"* quando as bases ou o rótulo não cobrem a pergunta.

**O que o sistema NÃO faz:**
- Diagnóstico médico, prescrição de dietas ou recomendação de doses de medicamentos.
- Planos alimentares individualizados (orienta procurar nutricionista).
- Recomendação de marcas ou produtos comerciais específicos.
- Afirmação de que um produto é "livre de alergênicos".
- Fora do escopo atual: identificação do símbolo `"T"` de transgênicos, leitura de código de barras / Open Food Facts e atividade física.

### 1.4 Arquitetura Aprovada (`APROVADO` em 11/11 e 13/11/2026)

| Camada / Componente MLOps | Tecnologia / Estratégia | Status Documental | Status no Repositório (14/11) |
|---|---|---|---|
| **Interface Mobile First** | React + Vite + Tailwind (navegador mobile) | `APROVADO` | `PENDENTE` (sem código entregue) |
| **API Central (C8 — Serving)** | Python + FastAPI (`main:api`) | `APROVADO` (ADR-003) | `IMPLEMENTADO` (esqueleto `POST /api/analyze`) |
| **Orquestração (C3 — Workflow)** | LangGraph com coordenador determinístico por regras | `APROVADO` (ADR-004) | `IMPLEMENTADO` (esqueleto sem regras reais) |
| **Extração de Rótulos** | Compressão no cliente → OpenCV → OCR (Tesseract ou PaddleOCR) → Regras + validação → Confirmação do usuário (LLM multimodal só como reserva) | `APROVADO PARCIALMENTE` (ADR-002; escolha do OCR pendente de benchmark) | `PENDENTE` |
| **Armazenamento Híbrido (C4 adaptado)** | PostgreSQL (TACO, limites IN 75, cache, métricas) + ChromaDB (RAG documental) | `APROVADO` (ADR-001) | `PROPOSTO` (containers em `compose.yaml`; integração no código `PENDENTE`) |
| **Verificação de Respostas** | Benchmark entre Config. A (sem verificador), Config. B (regras) e Config. C (LLM; fica se ≥ +5 pts fidelidade e ≤ +3 s latência sobre B) | `EM AVALIAÇÃO` / Regra `APROVADA` (ADR-005) | `IMPLEMENTADO` flag `enable_verifier` com lógica simulada |
| **Versionamento MLOps (C6/C7 adaptados)** | Git/GitHub para código, prompts, manifestos de execução e versões de índice (`base_conhecimento_v1`...) | `PROPOSTO PARA VALIDAÇÃO` (ADR-006) | `IMPLEMENTADO` estrutura inicial em `mlops/` e `snapshots/` |
| **CI/CD (C1)** | GitHub Actions (build, sintaxe, smoke tests, Docker) | `APROVADO` (ADR-007) | `IMPLEMENTADO` em `.github/workflows/ci.yml` |
| **Monitoramento (C9)** | Logs + tabela `metricas_requisicao` no PostgreSQL (1 linha/requisição); Grafana opcional na sem. 5; **sem Prometheus** | `APROVADO` (ADR-008) | `PROPOSTO` documentação em `mlops/monitoring/`; integração `PENDENTE` |

### 1.5 Papéis e Responsáveis (`APROVADO` em 11/11/2026)

| Integrante | Papéis (Kreuzberger et al., 2023) | Responsabilidades |
|---|---|---|
| **João Victor** | **R1** Stakeholder + **R2** Arquiteto | Essential Question, escopo, ADRs, 5 perguntas; **código:** coordenador por regras (LangGraph), agente de comparação, verificação por regras (Config. B) |
| **Gustavo (Líder)** | **R3** Cientista de Dados | Conjunto de teste (50 perguntas + ~30 fotos) e gabarito; benchmarks (LLM vs RAG, verificador A/B/C, OCR); avaliação com usuários; métricas |
| **Davi Rodrigues** | **R4** Engenheiro de Dados | Fontes oficiais; ingestão ChromaDB (`base_conhecimento_v1`); migrações PostgreSQL, TACO e limites IN 75; regras de extração OCR e checagens; cache de produtos |
| **Carlos** | **R5** Engenheiro de Software | API FastAPI; agente nutricional e verificador com LLM (Config. C); integração do OCR à API; aplicação web React Mobile First |
| **Caio Soares de Andrade** | **R6** DevOps + **R7** MLOps | Estrutura do repositório, preservação de baselines, Docker/Docker Compose, ambientes, CI/CD (GitHub Actions); versionamento de modelos/prompts/índices/configurações e monitoramento |

### 1.6 Requisitos Mobile First e Regras de Segurança (`APROVADO`)

- **Mobile First no navegador:** Captura, recorte e compressão no celular (~1280 px no maior lado, JPEG, até ~300 KB preservando legibilidade); OCR principal e agentes rodam no servidor.
- **Zero cálculo por LLM:** Todos os números vêm do PostgreSQL e de cálculos determinísticos em código.
- **Evidência obrigatória:** Toda afirmação cita trecho recuperado do RAG; sem suporte documental, responde *"não há evidência suficiente"*.
- **Limite de chamadas ao LLM:** No máximo 1 a 2 chamadas por resposta; o coordenador roteia por regras sem usar LLM.
- **Segurança alimentar e médica:** Nunca declarar produto "livre de alergênicos"; exigir confirmação do usuário para todos os dados extraídos via OCR; exibir aviso fixo de que o sistema não substitui médico ou nutricionista.
- **Privacidade (LGPD):** Não armazenar fotografias de rótulos nem perfil pessoal de saúde em bancos ou logs sem consentimento explícito.

### 1.7 Cronograma (`APROVADO`)

| Semana | Período | Foco | Entregável Principal |
|---|---|---|---|
| **1** | 26/10–01/11 | Problema, stakeholders, riscos, métricas | Definições do projeto |
| **2** | 02/11–08/11 | RAG e comparação LLM vs RAG | Base no ChromaDB, conjunto de teste, comparação medida |
| **3** | 09/11–15/11 | Multiagentes | TACO e limites no PostgreSQL; agentes com verificador ligável; benchmark do verificador |
| **4** | 16/11–22/11 | Multimodalidade | Pipeline OpenCV + OCR + regras; benchmark de extração (~30 fotos) |
| **5** | 23/11–29/11 | Integração | Aplicação funcional ponta a ponta; testes em celular (4G, tamanho/latência) |
| **6** | 30/11–06/12 | Testes e refinamento | Avaliação com usuários (5 a 10 pessoas), relatório e apresentação |
| **Final** | **07/12/2026** | Entrega final | Aplicação, relatório e apresentação |

### 1.8 Métricas de Validação (`APROVADO`)

| Métrica | Definição | Meta Inicial | Semana |
|---|---|---|---|
| **Acerto das respostas** | % de respostas corretas frente ao gabarito | RAG ≥ 15 pts percentuais acima do LLM puro | 2 |
| **Fidelidade às fontes** | % de afirmações sustentadas pelo trecho citado | ≥ 90% | 2 |
| **Recall da recuperação (top 3)** | % de perguntas com trecho correto no top 3 | ≥ 80% | 2 |
| **Recusa correta** | % de perguntas fora da base respondidas com "sem evidência" | ≥ 90% | 2 |
| **Ganho do verificador (LLM)** | Fidelidade e latência da Config. C vs Config. B | Adotar C só se ≥ +5 pts fidelidade e ≤ +3 s latência | 3 |
| **Acerto da extração (OCR)** | % de campos nutricionais lidos corretamente (~30 fotos) | ≥ 85% | 4 |
| **Custo/tempo da extração** | Tempo e recursos por foto | Comparativo Tesseract vs PaddleOCR vs Gemini Vision | 4 |
| **Tempo de resposta** | Latência mediana ponta a ponta em rede 4G | ≤ 10 s | 5 |
| **Chamadas ao LLM** | Média de invocações do LLM por requisição | ≤ 2 | 5 |
| **Avaliação de usuários** | Clareza e utilidade (escala de 1 a 5, 5–10 usuários) | ≥ 4,0 / 5,0 | 6 |

---

## 2. Estado do Desenvolvimento em 14/11/2026

### 2.1 Implementações Verificadas no Código (`IMPLEMENTADO`)
- **Esqueleto FastAPI (`backend/main.py`):** Endpoint `POST /api/analyze` funcional, contrato Pydantic validado (`backend/schemas.py`), medição de `response_time_ms` e flag `enable_verifier`.
- **Esqueleto de Grafo (`backend/graph.py`, `backend/state.py`):** Workflow LangGraph compilado com transição condicional para o nó `verifier`.
- **Infraestrutura do Repositório, Containers, CI e MLOps:**
  - Estrutura de diretórios padronizada do repositório;
  - Preservação auditável do baseline `backend-whatsapp-v0.1.0` com `SHA256SUMS`, `manifest.yaml` e `scripts/verify_baseline.py`;
  - Containerização do backend (`backend/Dockerfile`) e orquestração multi-serviço (`compose.yaml` com `backend`, `postgres` e `chromadb`);
  - Pipeline de Integração Contínua (`.github/workflows/ci.yml`) e script de smoke test (`scripts/smoke_backend.sh`);
  - Estrutura inicial MLOps (`mlops/manifests/runtime-manifest.yaml`, diretórios e convenções de prompts, experimentos e monitoramento).

### 2.2 Implementações Simuladas no Código (`SIMULADO`)
- `coordinator_node` em `backend/graph.py`: apenas imprime mensagem no console e retorna `{}`.
- `nutritional_agent_node` em `backend/graph.py`: retorna resposta, fonte, aviso e classificação hardcoded/simulados.
- `verifier_agent_node` em `backend/graph.py`: apenas verifica se a lista `matched_sources` não é vazia (`bool(state.get("matched_sources"))`), sem regras nutricionais nem chamada a LLM.

### 2.3 Decisões Aprovadas (`APROVADO`)
- Arquitetura híbrida PostgreSQL + ChromaDB (ADR-001).
- Pipeline de extração com compressão mobile, OpenCV, OCR tradicional, regras e confirmação obrigatória do usuário (ADR-002).
- FastAPI como camada central de processamento no servidor (ADR-003).
- LangGraph com coordenador por regras determinísticas e limite de ≤ 2 chamadas ao LLM (ADR-004).
- Regra de decisão experimental do verificador: Config. C (LLM) só permanece se ganhar ≥ 5 pontos percentuais de fidelidade sobre Config. B (regras) com ≤ 3 s de latência adicional (ADR-005).
- GitHub Actions para CI/CD (ADR-007).
- Monitoramento via logs + tabela `metricas_requisicao` no PostgreSQL, sem Prometheus e com Grafana opcional na semana 5 (ADR-008).

### 2.4 Decisões Pendentes (`PENDENTE`)
- Escolha definitiva entre **Tesseract** e **PaddleOCR** (depende do benchmark da semana 4 — ADR-002).
- Definição da configuração padrão de verificação (**Config. B por regras** vs **Config. C com LLM**, depende do benchmark da semana 3 — ADR-005).
- Validação final do mecanismo de versionamento de modelos, prompts e índices (ADR-006 está com status *"Proposto para validação"*).
- Definição do modelo de linguagem alternativo caso a cota gratuita do Gemini se esgote.
- Deliberação do grupo sobre ativar ou não as checagens SQL adicionais sugeridas por R4 (além de `açúcares totais <= carboidratos`).

### 2.5 Pendências por Papel da Equipe (R1 a R7)

- **R1 / R2 (João Victor — Negócio, Arquitetura e Orquestração):**
  - [x] Entregar `adr.pdf` (ADR-001 a ADR-008) e `5_perguntas_escopo_essential_question.pdf` atualizados.
  - [ ] Implementar coordenador determinístico por regras (`ocr_analysis`, `comparison`, `qa`) em `backend/graph.py`.
  - [ ] Implementar agente de comparação e verificador por regras determinísticas (Config. B).
- **R3 (Gustavo — Líder e Cientista de Dados):**
  - [ ] Revisar o rascunho do conjunto de teste (50 perguntas) e conferir o gabarito nas fontes oficiais.
  - [ ] Conferir os 6 limites da IN 75/2020 carregados por R4.
  - [ ] Executar os benchmarks (LLM vs RAG, Verificador A/B/C e OCR) e registrar resultados em `mlops/experiments/`.
- **R4 (Davi Rodrigues — Engenheiro de Dados):**
  - [x] Elaborar e testar o esquema do PostgreSQL (`001_fontes.sql` a `004_metricas.sql` e `migrate.sh`).
  - [x] Incorporar os arquivos de migração e seeds SQL neste repositório (`migrations/` e `seeds/`).
  - [x] Implementar módulos de integração com PostgreSQL (`backend/database.py`) e ChromaDB (`backend/chroma_client.py`).
  - [x] Documentar plano e matriz R4 em `docs/r4/documento_desafio2_r4.md` e `docs/r4/papel_R4_davi.xlsx`.
  - [x] Conferir conteúdo das fontes oficiais (`010_conferencia_fontes.sql` e `011_fontes_alergenicos.sql`); TACO real (`007_carga_taco.sql`) e os 6 limites literais da IN 75/2020 (`008_limites_in75.sql`) já carregados no PostgreSQL.
  - [x] Indexar o texto integral dos documentos oficiais no ChromaDB (`base_conhecimento_v2` via `scripts/ingest_chroma.py`, 1951 trechos de 500 chars / 100 overlap com normas extraídas de HTML oficial do DOU/Planalto e embeddings multilíngues).
  - [ ] Implementar as regras de extração e checagens de consistência do OCR (semana 4).
- **R5 (Carlos — Engenheiro de Software):**
  - [x] Entregar esqueleto inicial da API FastAPI e LangGraph (`backend-whatsapp-v0.1.0`).
  - [ ] Conectar o agente nutricional ao ChromaDB/PostgreSQL e implementar o verificador com LLM ligável (Config. C).
  - [ ] Integrar o pipeline de pré-processamento OpenCV e OCR à API FastAPI.
  - [ ] Desenvolver a aplicação web Mobile First (React + Vite + Tailwind) em `frontend/`.
- **R6 / R7 (Caio Soares de Andrade — DevOps e MLOps):**
  - [x] Estruturar o repositório, preservar o baseline `backend-whatsapp-v0.1.0` e os documentos de contexto.
  - [x] Implementar `backend/Dockerfile`, `compose.yaml`, `.env.example`, `.github/workflows/ci.yml` e `scripts/smoke_backend.sh`.
  - [x] Estruturar `mlops/manifests/runtime-manifest.yaml` e convenções de versionamento de prompts/índices/monitoramento.
  - [x] Integrar a execução automática das migrações SQL (`001`–`011`) no `compose.yaml` (volume `/docker-entrypoint-initdb.d`).
  - [ ] Habilitar o container e o job de CI do `frontend` assim que R5 entregar a aplicação React.
  - [ ] Avaliar na semana 5 a integração opcional do Grafana lendo do PostgreSQL.

---

## 3. Registro de Divergências entre Documentos de Origem

Durante a consolidação documental em 14/11/2026, foram registradas as seguintes observações entre `contextoCLAUDEV2.md`, `adr.pdf` e `5_perguntas_escopo_essential_question.pdf`:

1. **Atualização dos ADRs e das 5 Perguntas:** A seção 12 de `contextoCLAUDEV2.md` listava ajustes pendentes nos ADRs (como detalhar configs A/B/C no ADR-005 e aprovar ADR-007/ADR-008 com PostgreSQL sem Prometheus) e na resposta C9 das 5 perguntas. A inspeção dos arquivos `adr.pdf` e `5_perguntas_escopo_essential_question.pdf` recebidos em 14/11 comprova que **essas atualizações já foram incorporadas nesses dois PDFs**.
2. **Status formal do ADR-005 e ADR-006 em `adr.pdf`:**
   - **ADR-005** consta como *"Em avaliação"* porque a regra de decisão (+5 pts / ≤ 3 s) está aprovada, mas a escolha final entre B e C aguarda o resultado empírico do benchmark.
   - **ADR-006** consta como *"Proposto para validação"* quanto à ferramenta definitiva de metadados; portanto, a estrutura em `mlops/` mantém o versionamento leve em Git/YAML conforme a seção 3 do ADR-006, sem introduzir serviços extras (como MLflow) sem deliberação da equipe.
