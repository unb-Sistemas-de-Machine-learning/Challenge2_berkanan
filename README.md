# Challenge2_berkanan

Challenge 2 - Equipe Berkanan - Tópicos Especiais em Engenharia de Software - Sistemas de Machine Learning 2026/02

## Assistente Inteligente para Interpretação de Rótulos Nutricionais e Comparação de Alimentos

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-1C3C3C)](https://langchain-ai.github.io/langgraph/)
[![React](https://img.shields.io/badge/React-18_(Pendente)-61DAFB?logo=react&logoColor=white)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-5_(Pendente)-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-vector_store-FF6F61)](https://www.trychroma.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)

Projeto acadêmico de Sistemas de Machine Learning e MLOps cujo objetivo é auxiliar consumidores brasileiros na leitura de rótulos nutricionais, identificação de alergênicos e comparação entre alimentos no momento da compra pelo celular, combinando visão computacional (OpenCV + OCR), cálculos determinísticos em banco relacional (PostgreSQL) e explicação fundamentada em fontes oficiais via RAG (ChromaDB + LangGraph).

> **Aviso acadêmico:** este sistema possui caráter exclusivamente informativo e educacional e **não substitui** orientação médica ou nutricional profissional. Nunca afirma que um produto é livre de alergênicos e exige sempre a conferência da embalagem física.

**Acompanhamento do projeto:** [quadro no GitHub Projects](https://github.com/users/GustOki/projects/3), com as tarefas, os responsáveis e os prazos de cada semana.

---

## Sumário

- [Sobre o projeto](#sobre-o-projeto)
- [Objetivos, métricas de validação e estado atual](#objetivos-métricas-de-validação-e-estado-atual)
- [Conjunto de teste e benchmarks](#conjunto-de-teste-e-benchmarks)
- [Cronograma](#cronograma)
- [Arquitetura](#arquitetura)
- [Abordagem Mobile First e privacidade (LGPD)](#abordagem-mobile-first-e-privacidade-lgpd)
- [Stack técnica](#stack-técnica)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Quick start](#quick-start)
- [Endpoints da API](#endpoints-da-api)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Como funciona o pipeline](#como-funciona-o-pipeline)
- [Governança MLOps, versionamento e ADRs](#governança-mlops-versionamento-e-adrs)
- [Testes e CI/CD](#testes-e-cicd)
- [Deploy](#deploy)
- [Riscos e mitigações](#riscos-e-mitigações)
- [Limitações conhecidas](#limitações-conhecidas)
- [Equipe e referências](#equipe-e-referências)
- [Licença](#licença)

---

## Sobre o projeto

- **Big Idea:** *"Empoderando pessoas com IA para compreender melhor, decidir melhor e viver melhor"* (tema: Qualidade de Vida).
- **Problema:** as pessoas decidem o que comprar com base em rótulos nutricionais difíceis de ler, em marketing de embalagens e em redes sociais. A informação confiável existe (Guia Alimentar para a População Brasileira, normas da ANVISA RDC 429/2020 e IN 75/2020, OMS, SBD), mas está distribuída em documentos longos que ninguém consulta na hora da compra.
- **Essential Question (`APROVADO`):** *"Como a inteligência artificial pode usar os rótulos de produtos e fontes oficiais para ajudar a orientar os consumidores brasileiros a escolher opções mais saudáveis na sua alimentação de forma rápida e confiável?"*
- **Público-alvo:** consumidor adulto no supermercado, usando o navegador do celular. Grupo de maior atenção: pessoas com **diabetes** ou **hipertensão**.
- **Restrições do professor (obrigatórias em todo o trabalho):** entender o problema antes da solução; justificar decisões técnicas; explicitar riscos e limitações; validar com métricas objetivas; utilizar evidências confiáveis.
- **Entrega final:** 07/12/2026 (aplicação, relatório e apresentação).

**Escopo aprovado (o que o sistema faz):**
- Lê a foto do rótulo nutricional e explica o produto: valor energético, carboidratos, açúcares totais e adicionados, proteínas, gorduras (totais, saturadas e trans), fibra alimentar, sódio, %VD (percentual de valores diários) e grau de processamento.
- Avisa se o produto declara alergênicos (ex.: lactose, glúten) lendo a seção `"ALÉRGICOS"` do rótulo, sempre exigindo que o usuário confira na embalagem física.
- Compara dois produtos na mesma base (100 g/ml) e indica o mais adequado segundo os critérios normativos, citando a fonte oficial.
- Responde dúvidas sobre alimentação com base nas fontes oficiais indexadas no RAG.
- Emite avisos específicos para quem informa ter diabetes ou hipertensão.
- Responde explicitamente `"não há evidência suficiente"` quando a base de conhecimento ou o rótulo não cobrem a pergunta.

**Fora do escopo (o que o sistema NÃO faz):**
- Diagnósticos clínicos, prescrição de dietas ou recomendação de doses de medicamentos.
- Planos alimentares individualizados (encaminha a um nutricionista).
- Recomendação de marcas ou produtos comerciais específicos.
- Afirmar que um produto é completamente "livre de alergênicos".
- Identificação de símbolo `"T"` de transgênicos, leitura de código de barras / Open Food Facts e recomendações sobre atividade física.

---

## Objetivos, métricas de validação e estado atual

### Metas experimentais e de validação (`APROVADO`)

As metas abaixo guiam os benchmarks conduzidos por **R3 (Cientista de Dados)** ao longo das semanas 2 a 6. São uma proposta inicial, a ajustar após a primeira medição. Nenhuma foi medida até 14/11, porque o backend ainda está em modo simulado:

| Métrica | O que mede | Meta inicial | Semana | Status em 14/11 |
|---|---|---|---|---|
| **Acerto das respostas** | % de respostas corretas frente ao gabarito (50 perguntas) | RAG ≥ 15 pontos acima do LLM puro | 2 | `PENDENTE` |
| **Fidelidade às fontes** | % de afirmações sustentadas pelo trecho citado | ≥ 90% | 2 | `PENDENTE` |
| **Recall da recuperação (top 3)** | % com o trecho correto entre os 3 primeiros do ChromaDB | ≥ 80% | 2 | `PENDENTE` |
| **Recusa correta** | % de perguntas fora da base respondidas com `"não há evidência suficiente"` | ≥ 90% | 2 | `PENDENTE` |
| **Ganho do verificador (LLM)** | Comparativo entre Config. A (sem), B (regras) e C (LLM) | Adotar C só se ganhar **≥ +5 pts** de fidelidade sobre B com **≤ +3 s** de latência | 3 | `PENDENTE` (ferramenta pronta; aguardando backend real) |
| **Acerto da extração (OCR)** | % de campos lidos corretamente (~30 fotos de rótulos) | ≥ 85% | 4 | `PENDENTE` |
| **Custo/tempo da extração** | Tempo e recursos por foto | Comparativo Tesseract vs PaddleOCR vs Gemini Vision | 4 | `PENDENTE` |
| **Tempo de resposta** | Latência mediana ponta a ponta em rede móvel 4G | ≤ 10 s | 5 | `PENDENTE` |
| **Chamadas ao LLM** | Média de invocações ao LLM por resposta | ≤ 2 | 5 | `PENDENTE` (a API ainda não informa as chamadas) |
| **Avaliação de usuários** | Clareza e utilidade (5 a 10 pessoas) | ≥ 4,0 de 5,0 | 6 | `PENDENTE` |

### Objetivos x entregas (estado em 14/11/2026)

| Frente / Entrega | Status | Evidência no repositório |
|---|---|---|
| **Preservação do baseline do backend (`whatsapp-v0.1.0`)** | `IMPLEMENTADO` | Snapshot imutável em [snapshots/backend/whatsapp-v0.1.0/](snapshots/backend/whatsapp-v0.1.0), hashes em `SHA256SUMS` e validador [scripts/verify_baseline.py](scripts/verify_baseline.py). |
| **Preservação de contexto e ADRs (001 a 008)** | `IMPLEMENTADO` | Fontes originais em [docs/context/sources/](docs/context/sources), índice [docs/context/INDEX.md](docs/context/INDEX.md) e manifesto [docs/context/MANIFEST.yaml](docs/context/MANIFEST.yaml). |
| **API Backend FastAPI (`POST /api/analyze`)** | `IMPLEMENTADO` (Esqueleto) | Aplicação `main:api` em [backend/main.py](backend/main.py) e contratos Pydantic em [backend/schemas.py](backend/schemas.py). |
| **Orquestração LangGraph com verificador ligável** | `SIMULADO` (Esqueleto) | Fluxo `coordinator` → `nutritional` → `verifier` compilado em [backend/graph.py](backend/graph.py), retornando dados simulados (mock) nesta versão inicial. |
| **Containerização Docker e Docker Compose** | `IMPLEMENTADO` | [backend/Dockerfile](backend/Dockerfile) e [compose.yaml](compose.yaml) orquestrando `backend`, `postgres` (PostgreSQL 16) e `chromadb` com volumes e healthchecks. |
| **CI/CD com GitHub Actions e Smoke Tests** | `IMPLEMENTADO` | Pipeline [.github/workflows/ci.yml](.github/workflows/ci.yml) e script [scripts/smoke_backend.sh](scripts/smoke_backend.sh). |
| **Estrutura MLOps (manifesto, prompts, índices, monitoramento)** | `IMPLEMENTADO` | Manifesto [mlops/manifests/runtime-manifest.yaml](mlops/manifests/runtime-manifest.yaml) e convenções em [mlops/](mlops). |
| **Ferramentas de benchmark (R3)** | `IMPLEMENTADO` (sem resultados oficiais) | Validador do conjunto de teste, executor A/B/C contra a API e cálculo das métricas e da decisão C x B em [mlops/experiments/benchmark/](mlops/experiments/benchmark). |
| **Conjunto de teste (50 perguntas)** | `RASCUNHO` fora do repo | Em revisão por R3; gabarito ainda não conferido nas fontes oficiais. Modelo do CSV em [mlops/experiments/testset/](mlops/experiments/testset). |
| **Migrações SQL (TACO, limites IN 75, `metricas_requisicao`)** | `PENDENTE` no repo | Esquema revisado por R4 fora do repositório; aguardando inclusão dos arquivos `.sql` e conexão no código do backend. |
| **Ingestão RAG no ChromaDB (`base_conhecimento_v1`)** | `PENDENTE` | Container ChromaDB pronto; aguardando ingestão das 5 fontes oficiais por R4. |
| **Pipeline OpenCV + OCR + confirmação do usuário** | `PENDENTE` | Aguardando benchmark da semana 4 e integração por R4/R5. |
| **Frontend Web Mobile First (React + Vite + Tailwind)** | `PENDENTE` | Diretório [frontend/](frontend) documentado, aguardando entrega do código por R5. |

Pendências detalhadas por pessoa, com responsável, prazo e dependências: [quadro do projeto no GitHub Projects](https://github.com/users/GustOki/projects/3) (issues #2 a #24). Resumo consolidado em [docs/context/INDEX.md](docs/context/INDEX.md).

---

## Conjunto de teste e benchmarks

### Conjunto de teste (`RASCUNHO`, em revisão por R3)

São 50 perguntas com as colunas `ID, Categoria, Pergunta, Resposta esperada (gabarito), Fonte esperada, Comportamento esperado, Métrica, Conferir na fonte`. O mesmo conjunto serve aos benchmarks LLM x RAG e do verificador. O benchmark de extração usará cerca de 30 fotos de rótulos.

| Prefixo | Categoria | Qtd. | Mede |
|---|---|---|---|
| A | Guia Alimentar | 10 | Acerto, fidelidade, recall |
| B | Rotulagem ANVISA | 10 | Acerto, fidelidade, recall |
| C | Cálculo "ALTO EM" (inclui normalização por porção e leitura inconsistente) | 8 | Acerto |
| D | Comparação de dois produtos | 6 | Acerto, fidelidade |
| E | Alergênicos | 5 | Acerto, segurança |
| F | Saúde e OMS (diabetes, hipertensão) | 5 | Acerto, segurança |
| G | Fora do escopo (dose, dieta, marca, transgênico, sem evidência) | 6 | Recusa correta |

O gabarito foi escrito de memória e **precisa ser conferido nas fontes oficiais** antes de valer como referência. As linhas com `Conferir na fonte = Sim` são as de menor certeza. Os produtos das categorias C e D são fictícios.

### Benchmark do verificador (ADR-005)

Mesmo conjunto de teste, mesmo modelo, temperatura 0 e 3 repetições para cada configuração:

| Config. | Verificação |
|---|---|
| A | Sem verificador |
| B | Por regras, sem LLM: todo número existe na base estruturada e toda resposta cita um trecho recuperado |
| C | Agente verificador com LLM |

A configuração C só fica se aumentar a fidelidade em ≥ 5 pontos sobre B, sem somar mais de 3 s à resposta. Caso contrário, fica B. **Status em 14/11:** não iniciado. Depende das bases (R4), do coordenador e do agente de comparação (R2) e do agente nutricional com verificador ligável (R5).

### Ferramentas ([mlops/experiments/benchmark/](mlops/experiments/benchmark))

Usam só a biblioteca padrão do Python. Rodar de dentro de `mlops/experiments/`:

```bash
python -m benchmark.testset testset/conjunto_de_teste.csv --strict      # valida o CSV
python -m benchmark.run --testset testset/conjunto_de_teste.csv \
    --configs A B C --reps 3 --api http://127.0.0.1:8000               # executa e gera a planilha de correção
python -m benchmark.metrics results/<experimento>/correcao.csv          # métricas e decisão C x B
python -m unittest discover -s tests -t .                               # testes das ferramentas
```

Com o backend em modo simulado, o executor marca o experimento como não oficial (`"official": false`), e esse resultado não vale como evidência. Detalhes e regras de correção estão em [mlops/experiments/README.md](mlops/experiments/README.md).

---

## Cronograma

| Semana | Período | Foco | Entregável |
|---|---|---|---|
| 1 | 26/10–01/11 | Problema, stakeholders, riscos, métricas | Definições do projeto |
| 2 | 02/11–08/11 | RAG e comparação LLM x RAG | Base no ChromaDB, conjunto de teste, comparação medida |
| 3 | 09/11–15/11 | Multiagentes | TACO e limites no PostgreSQL; agentes com verificador ligável; benchmark do verificador |
| 4 | 16/11–22/11 | Multimodalidade | Pipeline OCR + regras; benchmark de extração (~30 fotos) |
| 5 | 23/11–29/11 | Integração | Aplicação funcional; testes no celular (tempo e tamanho da imagem) |
| 6 | 30/11–06/12 | Testes e refinamento | Avaliação com usuários, relatório, apresentação |
| — | 07/12 | Entrega final | Aplicação, relatório e apresentação |

Feriado: 20/11.

---

## Arquitetura

A arquitetura aprovada em 11/11 e 13/11/2026 ([ADR-001 a ADR-008](docs/context/sources/adr.pdf)) divide o sistema em um cliente web leve para celular e um servidor central que concentra OCR, bancos de dados e orquestração multiagentes:

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                 NAVEGADOR MOBILE — React + Vite + Tailwind               │
│   1. Captura a foto do rótulo, recorta e comprime (~1280px, JPEG <=300KB)│
│   2. Exibe campos extraídos pelo OCR para CONFIRMAÇÃO OBRIGATÓRIA        │
│   3. Apresenta análise fundamentada, fontes citadas e avisos de saúde    │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ HTTP / HTTPS (POST /api/analyze)
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                BACKEND CENTRAL — FastAPI (backend/main.py)               │
│   Recebe requisições · Valida contratos Pydantic · Mede latência (ms)    │
└─────────────────┬──────────────────────────────────┬─────────────────────┘
                  │ 1. Extração (quando há foto)     │ 2. Análise (LangGraph)
                  ▼                                  ▼
┌────────────────────────────────────┐   ┌─────────────────────────────────┐
│ PIPELINE DE IMAGEM E OCR (ADR-002) │   │ COORDENADOR POR REGRAS (ADR-004)│
│ • OpenCV (cinza, inclinação, bin.) │   │ • Roteia sem chamar o LLM       │
│ • OCR CPU: Tesseract ou PaddleOCR  │   │ • Limite: <= 2 chamadas LLM/resp│
│ • Regras regex + validação 4C+4P+9G│   └───────────────┬─────────────────┘
│ • Reserva: LLM multimodal se falhar│                   │
└────────────────────────────────────┘                   ▼
                                         ┌─────────────────────────────────┐
                                         │ AGENTES: NUTRICIONAL/COMPARAÇÃO │
                                         │ • Zero cálculo numérico por LLM │
                                         └───────┬───────────────┬─────────┘
                                                 │               │
                         ┌───────────────────────┘               └─────────┐
                         ▼                                                 ▼
┌────────────────────────────────────────────────┐ ┌───────────────────────┐
│ POSTGRESQL 16 — Dados Estruturados (ADR-001/08)│ │ CHROMADB — RAG        │
│ • taco_alimentos (por 100 g)                   │ │ • base_conhecimento_v1│
│ • limites_rotulagem ("ALTO EM" — IN 75/2020)   │ │ • Guia Alimentar,     │
│ • produtos_lidos (cache + seção ALÉRGICOS)     │ │   RDC 429, IN 75,     │
│ • metricas_requisicao (1 linha por requisição) │ │   OMS e SBD           │
└────────────────────────────────────────────────┘ └───────────────────────┘
                                                 │
                                                 ▼
                                         ┌─────────────────────────────────┐
                                         │ VERIFICADOR OPCIONAL (ADR-005)  │
                                         │ • Config A: desligado           │
                                         │ • Config B: regras em código    │
                                         │ • Config C: agente LLM          │
                                         └─────────────────────────────────┘
```

**Regras arquiteturais inegociáveis (`APROVADO`):**
- **Todo número vem do PostgreSQL ou do rótulo confirmado via código determinístico:** o LLM apenas explica os resultados; nunca calcula nem inventa valores nutricionais.
- **Toda resposta cita a fonte oficial:** sem trecho recuperado no RAG, o sistema responde `"não há evidência suficiente"`.
- **Coordenador sem LLM:** o roteamento entre leitura de rótulo, dúvida geral ou comparação é feito por regras em código, mantendo o consumo em no máximo **1 a 2 chamadas ao LLM por resposta**.
- **Verificador configurável (`enable_verifier`):** a Configuração C (verificador com LLM) só permanece se vencer a Configuração B (regras) no benchmark por **≥ +5 pontos percentuais de fidelidade** e **≤ +3 segundos de latência adicional**.

---

## Abordagem Mobile First e privacidade (LGPD)

1. **Processamento no servidor:** celulares intermediários e redes móveis 4G possuem restrições de memória, bateria e banda. Por isso, não há OCR no dispositivo nem aplicativo nativo Android/iOS ou PWA; o navegador mobile apenas captura e comprime a imagem (**~1280 px no maior lado, formato JPEG, até ~300 KB**).
2. **Confirmação obrigatória pelo usuário:** erros de leitura óptica em embalagens curvas, amassadas ou com reflexo são mitigados exigindo que o usuário confira e confirme os valores extraídos (incluindo a seção `"ALÉRGICOS"`) antes do cálculo nutricional.
3. **Privacidade e LGPD:** o sistema **não armazena fotografias de rótulos nem perfis pessoais de saúde identificáveis** (`has_diabetes`, `has_hypertension`) em bancos de dados ou logs de containers sem consentimento explícito.
4. **HTTPS obrigatório para câmera:** navegadores móveis exigem contexto seguro (`https://`) para liberar `navigator.mediaDevices.getUserMedia()` fora de `localhost` (documentado em [docs/architecture/DEPLOYMENT.md](docs/architecture/DEPLOYMENT.md)).

---

## Stack técnica

### Backend e MLOps

| Camada | Tecnologia | Status no repositório |
|---|---|---|
| API | Python 3.12 + FastAPI + Uvicorn (`main:api`) | `IMPLEMENTADO` (esqueleto) |
| Validação de contratos | Pydantic v2 | `IMPLEMENTADO` |
| Orquestração de agentes | LangGraph + LangChain Core | `IMPLEMENTADO` (esqueleto) |
| Pré-processamento de imagem | OpenCV | `APROVADO` / `PENDENTE` |
| OCR em CPU | Tesseract ou PaddleOCR (definido no benchmark da semana 4) | `EM AVALIAÇÃO` / `PENDENTE` |
| Vector store (RAG) | ChromaDB (`chromadb/chroma:0.5.20`) + embeddings HuggingFace | Container `IMPLEMENTADO` / Ingestão `PENDENTE` |
| Banco relacional e métricas | PostgreSQL 16 (`postgres:16.4-alpine`) | Container `IMPLEMENTADO` / Migrações `PENDENTES` |
| LLM | Google Gemini (com modelo alternativo configurável) | `APROVADO` / Integração `PENDENTE` |
| Containerização e CI/CD | Docker Compose + GitHub Actions | `IMPLEMENTADO` |
| Monitoramento | Logs + PostgreSQL (`metricas_requisicao`); Grafana opcional na sem. 5; **sem Prometheus** | `APROVADO` |

### Frontend (Previsto — R5)

| Camada | Tecnologia | Status no repositório |
|---|---|---|
| Framework | React 18 | `PENDENTE` |
| Build | Vite 5 | `PENDENTE` |
| Estilo | Tailwind CSS (Mobile First) | `PENDENTE` |

---

## Estrutura do repositório

```text
Challenge2_berkanan/
├── .github/
│   └── workflows/
│       └── ci.yml                 # Pipeline GitHub Actions (baseline, sintaxe, smoke test, Docker e Compose)
├── backend/                       # Código executável canônico do backend FastAPI e LangGraph
│   ├── main.py                    # Ponto de entrada FastAPI (uvicorn main:api), rota POST /api/analyze
│   ├── graph.py                   # Workflow LangGraph (coordinator -> nutritional -> verifier opcional)
│   ├── state.py                   # AgentState (TypedDict) compartilhado entre os nós
│   ├── schemas.py                 # Modelos Pydantic (AnalysisRequest, AnalysisResponse, etc.)
│   ├── requirements.txt           # Dependências Python atuais do backend
│   ├── test_api.sh                # Script manual original de teste com curl
│   ├── Dockerfile                 # Imagem Python 3.12.7-slim-bookworm (execução não-root)
│   └── README.md                  # Instruções originais do backend
├── frontend/
│   └── README.md                  # Requisitos Mobile First aguardando implementação React/Vite (R5)
├── infra/
│   ├── scripts/check_compose.sh   # Validação sintática e de variáveis do compose.yaml
│   └── README.md                  # Guia de infraestrutura e operação (R6)
├── mlops/
│   ├── manifests/
│   │   └── runtime-manifest.yaml  # Manifesto de versões (LLM, prompts, índice ChromaDB, OCR, commit)
│   ├── prompts/README.md          # Convenção de versionamento de prompts dos agentes
│   ├── experiments/
│   │   ├── benchmark/             # Validador do conjunto de teste, executor A/B/C e métricas (R3)
│   │   ├── testset/               # Modelo do CSV do conjunto de teste
│   │   ├── tests/                 # Testes das ferramentas de benchmark (unittest)
│   │   └── README.md              # Rastreabilidade dos índices (base_conhecimento_v1...) e benchmarks
│   ├── monitoring/README.md       # Estratégia de observabilidade no PostgreSQL (ADR-008)
│   └── README.md                  # Mapeamento dos 9 componentes MLOps (C1–C9) no projeto
├── docs/
│   ├── context/
│   │   ├── sources/               # Cópias integrais de contextoCLAUDEV2.md, adr.pdf e 5_perguntas.pdf
│   │   ├── AGENTS.md              # Orientação global compartilhada para agentes e colaboradores (R1–R7)
│   │   ├── INDEX.md               # Índice canônico consolidado do projeto em 14/11/2026
│   │   └── MANIFEST.yaml          # Hashes SHA-256 dos documentos e relação com ADRs
│   ├── architecture/
│   │   └── DEPLOYMENT.md          # Topologia de containers, redes, volumes e requisitos Mobile First
│   ├── baselines/
│   │   └── backend-whatsapp-v0.1.0.md # Histórico e auditoria do baseline recebido via WhatsApp
│   └── handoff/
│       └── RESPONSIBILITIES.md    # Divisão de papéis R1–R7 e pontos de handoff da equipe
├── snapshots/
│   └── backend/
│       └── whatsapp-v0.1.0/       # Preservação histórica imutável do backend original
│           ├── original/          # Os 7 arquivos originais intocados (incluindo README(1).md)
│           ├── SHA256SUMS         # Hashes SHA-256 originais
│           └── manifest.yaml      # Metadados completos do baseline e commit Git raiz
├── scripts/
│   ├── verify_baseline.py         # Comprova integridade SHA-256 do snapshot e fontes de contexto
│   └── smoke_backend.sh           # Smoke test automatizado com asserções HTTP/JSON para POST /api/analyze
├── compose.yaml                   # Orquestração Docker Compose (backend, postgres, chromadb)
├── .env.example                   # Exemplo de variáveis de ambiente (sem credenciais sensíveis)
├── .gitignore                     # Exclusão de .env, ambientes virtuais, volumes e imagens temporárias
├── AGENTS.md                      # Guia obrigatório de governança para agentes de IA
├── CLAUDE.md                      # Ponto de entrada conciso para o Claude Code
└── README.md                      # Documentação principal do repositório
```

---

## Quick start

### Pré-requisitos

| Ferramenta | Versão recomendada | Verificação |
|---|---|---|
| Python | 3.10+ (testado em 3.12) | `python3 --version` |
| Docker | 24+ | `docker --version` |
| Docker Compose | v2.20+ | `docker compose version` |

### 1. Clone o repositório e verifique a integridade do baseline

```bash
git clone https://github.com/unb-Sistemas-de-Machine-learning/Challenge2_berkanan.git
cd Challenge2_berkanan

# Comprova os hashes SHA-256 do snapshot original e dos documentos de contexto
python3 scripts/verify_baseline.py
```

### 2. Executar o backend localmente (ambiente Python)

```bash
python3 -m venv .venv
source .venv/bin/activate              # Linux/macOS
# ou: source .venv/Scripts/activate   # Git Bash (Windows)

python3 -m pip install --upgrade pip
python3 -m pip install -r backend/requirements.txt

cd backend
uvicorn main:api --reload --host 0.0.0.0 --port 8000
```

Em outro terminal, valide a API com o smoke test automatizado:

```bash
bash scripts/smoke_backend.sh
```

### 3. Executar via Docker Compose (`backend` + `postgres` + `chromadb`)

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps                     # verificar status "healthy"

# Rodar smoke tests contra o container
bash scripts/smoke_backend.sh
```

### Fluxo resumido (copiar e colar)

```bash
python3 scripts/verify_baseline.py
cp .env.example .env
docker compose up --build -d
bash scripts/smoke_backend.sh
```

---

## Endpoints da API

| Método | Rota | Descrição | Request | Response |
|---|---|---|---|---|
| `POST` | `/api/analyze` | Executa o fluxo LangGraph para análise nutricional, comparação ou dúvida | `AnalysisRequest` | `AnalysisResponse` |
| `GET` | `/docs` | Documentação interativa Swagger UI | — | HTML |
| `GET` | `/openapi.json` | Especificação OpenAPI 3 (usada também no healthcheck do container) | — | JSON |

### Exemplo com `curl`

```bash
# Com verificador habilitado (enable_verifier: true)
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "request_type": "ocr_analysis",
    "enable_verifier": true,
    "user_profile": {"has_diabetes": true, "has_hypertension": false}
  }'
```

### Contrato `AnalysisRequest` ([backend/schemas.py](backend/schemas.py))

| Campo | Tipo | Padrão | Significado |
|---|---|---|---|
| `request_type` | `"ocr_analysis"` \| `"comparison"` \| `"qa"` | `"ocr_analysis"` | Tipo de operação solicitada ao coordenador |
| `text` | `string \| null` | `null` | Pergunta textual do usuário |
| `image_base64` | `string \| null` | `null` | Imagem do rótulo comprimida em base64 (pipeline OCR pendente) |
| `product_ids` | `string[] \| null` | `null` | Identificadores de produtos para comparação |
| `user_profile` | `{has_diabetes: bool, has_hypertension: bool}` | `{false, false}` | Condições informadas para emissão de alertas |
| `enable_verifier` | `bool` | `true` | Liga ou desliga o nó verificador no LangGraph |

### Contrato `AnalysisResponse` ([backend/schemas.py](backend/schemas.py))

| Campo | Tipo | Significado |
|---|---|---|
| `id` | `UUID \| null` | Identificador da requisição |
| `input_text` | `string \| null` | Texto analisado ou `"Análise de rótulo"` |
| `llm_explanation` | `string \| null` | Explicação gerada pelo agente nutricional |
| `matched_sources` | `[{text, source, similarity, source_url, source_title}]` | Fontes oficiais recuperadas para sustentar a resposta |
| `timestamp` | `datetime` | Data/hora UTC da resposta |
| `response_time_ms` | `int` | Tempo de processamento em milissegundos |
| `classification` | `"SAUDAVEL"` \| `"ATENCAO"` \| `"EVITAR"` \| `"INCONCLUSIVO"` \| `"ERRO"` | Tom de recomendação calculado |
| `confidence_score` | `float` | Pontuação de confiança (`1.0` se aprovado na verificação, `0.5` caso contrário) |
| `rag_sources_count` | `int` | Quantidade de fontes retornadas em `matched_sources` |
| `extracted_data` | `{product_name, values_per_100g} \| null` | Dados nutricionais extraídos do rótulo |
| `warnings` | `string[]` | Alertas nutricionais ou clínicos (ex.: alto teor de açúcar para diabéticos) |
| `verification` | `{passed: bool, errors: string[]} \| null` | Resultado do verificador (`null` quando `enable_verifier=false`) |

---

## Variáveis de ambiente

Definidas em [.env.example](.env.example) (nunca commitar `.env` com segredos reais):

| Variável | Padrão em `.env.example` | Descrição |
|---|---|---|
| `APP_ENV` | `development` | Ambiente de execução (`development` / `production`) |
| `LOG_LEVEL` | `INFO` | Nível de log da aplicação |
| `BACKEND_HOST_BIND` / `BACKEND_PORT` | `127.0.0.1` / `8000` | Endereço e porta de publicação do container `backend` |
| `MAX_UPLOAD_BYTES` | `307200` | Limite de referência para imagem comprimida no celular (300 KB) |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `postgres` / `5432` | Host e porta do PostgreSQL na rede interna do Docker Compose |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `berkanan_dev` / `berkanan_user` / `dev_only_change_me` | Credenciais de desenvolvimento do PostgreSQL |
| `CHROMA_HOST` / `CHROMA_PORT` | `chromadb` / `8000` | Host e porta interna do ChromaDB |
| `CHROMA_COLLECTION` | `base_conhecimento_v1` | Identificador versionado da coleção vetorial (ADR-006) |
| `EMBEDDING_MODEL` | `not_configured` | Modelo de embeddings HuggingFace (a configurar por R4) |
| `LLM_PROVIDER` / `LLM_MODEL` | `gemini` / `not_configured` | Provedor principal e versão do modelo de linguagem |
| `LLM_FALLBACK_MODEL` | `not_configured` | Modelo alternativo caso a cota gratuita do Gemini se esgote |
| `GEMINI_API_KEY` | `replace_with_your_local_key_do_not_commit` | Chave de API do Google Gemini |
| `ENABLE_VERIFIER_DEFAULT` | `true` | Estado padrão do verificador (`enable_verifier`) |
| `OCR_ENGINE` | `not_configured` | Ferramenta de OCR (`tesseract` ou `paddleocr`, pós-benchmark) |

---

## Como funciona o pipeline

### 1. Extração de rótulos por OCR e regras (`APROVADO` no ADR-002 — implementação `PENDENTE`)

1. **Dispositivo móvel:** recorta a tabela nutricional e comprime a imagem para JPEG (~1280 px, até 300 KB).
2. **Pré-processamento (OpenCV):** conversão para escala de cinza, correção de inclinação e binarização.
3. **OCR em CPU:** Tesseract (português) ou PaddleOCR, definido pelo benchmark da semana 4 (~30 fotos reais, meta ≥ 85% de acerto).
4. **Extração e validação por regras:** expressões regulares extraem valor energético, carboidratos, açúcares totais e adicionados, proteínas, gorduras (totais, saturadas e trans), fibra, sódio, %VD e a seção `"ALÉRGICOS"`, normalizando para 100 g/ml e checando consistência (`açúcares totais <= carboidratos` e estimativa energética `4×C + 4×P + 9×G`).
5. **Reserva multimodal e confirmação:** se a leitura falhar, aciona o LLM multimodal apenas nessa foto ou solicita correção ao usuário. **Em todos os casos, o usuário confirma os valores antes da análise.**

### 2. Orquestração LangGraph ([backend/graph.py](backend/graph.py) — ADR-004)

- **Coordenador (`coordinator_node`):** identifica o tipo de requisição (`ocr_analysis`, `comparison`, `qa`) por regras determinísticas, sem gastar chamada ao LLM.
- **Agente Nutricional / Comparação:** consulta os limites da IN 75/2020 e a tabela TACO no PostgreSQL via SQL/código determinístico e recupera os trechos normativos no ChromaDB (`base_conhecimento_v1`) para que o LLM redija a explicação citada. *(No baseline `v0.1.0`, retorna dados simulados).*
- **Agente Verificador (`verifier_agent_node`):** habilitado quando `enable_verifier=true`.

### 3. Monitoramento no PostgreSQL (ADR-008)

- Cada requisição processada registrará uma linha na tabela `metricas_requisicao` do PostgreSQL com latência por etapa, falhas de leitura do OCR, quantidade de chamadas ao LLM, versão do OCR, modelo usado e configuração do verificador (`A`, `B` ou `C`).
- Consultas SQL e views (`vw_*`) verificam os limiares operacionais (acerto < 85% ou fidelidade < 90%) sem necessidade de Prometheus.

---

## Governança MLOps, versionamento e ADRs

Como o projeto utiliza modelos existentes sem treinamento de pesos próprios, o ciclo MLOps foi adaptado ([5_perguntas_escopo_essential_question.pdf](docs/context/sources/5_perguntas_escopo_essential_question.pdf) e [mlops/README.md](mlops/README.md)):

- **Model Registry adaptado (C6):** controla versões de modelos externos, prompts ([mlops/prompts/](mlops/prompts)), configurações de inferência e coleções do ChromaDB (`base_conhecimento_v1`, `base_conhecimento_v2`...) no manifesto [mlops/manifests/runtime-manifest.yaml](mlops/manifests/runtime-manifest.yaml).
- **Gatilhos de atualização ("retreinamento" adaptado):** não há retreinamento por agenda; a reindexação das bases e o ajuste de regras/prompts são disparados por **limiar de desempenho** (acerto da extração < 85% ou fidelidade às fontes < 90%) ou pela **entrada de novos documentos oficiais**.
- **Rastreabilidade de baselines:** o estado original recebido pelo WhatsApp está congelado em [snapshots/backend/whatsapp-v0.1.0/](snapshots/backend/whatsapp-v0.1.0) e documentado em [docs/baselines/backend-whatsapp-v0.1.0.md](docs/baselines/backend-whatsapp-v0.1.0.md).

---

## Testes e CI/CD

```bash
# 1. Verificar integridade SHA-256 do snapshot original e dos PDFs/MD de contexto
python3 scripts/verify_baseline.py

# 2. Validar compilação sintática dos módulos Python
python3 -m py_compile backend/main.py backend/graph.py backend/schemas.py backend/state.py scripts/verify_baseline.py

# 3. Validar configuração do Docker Compose
bash infra/scripts/check_compose.sh

# 4. Executar smoke test automatizado (valida HTTP 200, JSON e contrato com enable_verifier=true e false)
bash scripts/smoke_backend.sh

# 5. Testes das ferramentas de benchmark (R3)
cd mlops/experiments && python3 -m unittest discover -s tests -t .
```

A pipeline do GitHub Actions em [.github/workflows/ci.yml](.github/workflows/ci.yml) executa automaticamente as etapas 1 a 4, além do build da imagem Docker do backend e teste do container em cada `push` e `pull_request`. Os testes do benchmark (etapa 5) ainda não estão no CI.

> **Windows:** com `core.autocrlf=true`, o Git converte as quebras de linha no checkout e `verify_baseline.py` acusa hash divergente localmente, embora o conteúdo commitado esteja correto (no CI, em Linux, passa).

---

## Deploy

### Ambiente local / homologação com Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

Sobe os três serviços na rede interna `berkanan_internal`:
- `berkanan-backend` (FastAPI na porta `127.0.0.1:8000`)
- `berkanan-postgres` (PostgreSQL 16.4 na porta `127.0.0.1:5432`, volume `postgres_data`)
- `berkanan-chromadb` (ChromaDB 0.5.20 na porta `127.0.0.1:8001` → `8000` interna, volume `chroma_data`)

Detalhes operacionais e requisitos para testes em celulares reais (HTTPS, limite de upload de 300 KB e rede 4G) estão em [docs/architecture/DEPLOYMENT.md](docs/architecture/DEPLOYMENT.md).

---

## Riscos e mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| Alucinação sobre nutrição | Alto | Citação obrigatória; números da base estruturada; verificação; "não há evidência suficiente" |
| OCR erra (foto torta, borrada, reflexo, embalagem curva) | Alto | OpenCV; checagens de consistência; LLM com visão como reserva; confirmação do usuário |
| Usuário trata a resposta como orientação médica | Alto | Aviso fixo; triagem; encaminhamento a profissional |
| Alergênico não detectado (falso negativo) | Alto | Nunca afirmar "livre de alergênicos"; aviso para conferir a embalagem; medir acerto da linha "ALÉRGICOS" |
| Verificador não compensa custo e latência | Médio | Decidir pelo benchmark; regras como alternativa gratuita |
| App lento ou pesado no celular | Médio | Processamento no servidor; imagem comprimida; poucas chamadas ao LLM |
| Projeto parecido demais com o Desafio 1 | Médio | Foco em decisão de compra e comparação, não em checagem de fatos |
| Cota gratuita do Gemini esgota | Médio | Modelo alternativo; cache |
| Dados pessoais de saúde | Médio | Não armazenar sem consentimento (LGPD) |

---

## Limitações conhecidas

**Decisões em aberto (`PENDENTE`):**
- Qual OCR fica (Tesseract ou PaddleOCR), definido no benchmark da semana 4.
- Modelo alternativo ao Gemini.
- Aprovação das checagens extras de consistência sugeridas por R4 (comentadas no SQL; só "açúcares totais ≤ carboidratos" está ativa).
- Contrato da API para separar as configurações B e C (proposta: campo `verifier_mode`) e informar as chamadas ao LLM por resposta (`llm_calls`).

**Estado atual do código (`backend-whatsapp-v0.1.0`):**
- **Agentes em modo simulado (mock):** `backend/graph.py` retorna resposta textual, fonte (`guia_alimentar_pag_45.pdf`), aviso e classificação fixos.
- **Coordenador sem roteamento real:** `coordinator_node` ainda não desvia entre análise de rótulo, comparação de dois produtos e pergunta aberta.
- **Verificador simplificado:** `verifier_agent_node` apenas checa `bool(state.get("matched_sources"))`, sem executar ainda as regras determinísticas completas (Config. B) nem chamada ao LLM (Config. C).
- **Sem conexão ativa com bancos no código Python:** embora `postgres` e `chromadb` subam via `compose.yaml`, `backend/main.py` e `backend/graph.py` ainda não consultam o PostgreSQL nem o ChromaDB.
- **Sem pipeline OCR integrado:** o campo `image_base64` existe no schema, mas ainda não passa por OpenCV ou Tesseract/PaddleOCR.
- **Frontend ausente:** a interface React + Vite + Tailwind ainda será entregue em `frontend/`.

---

## Equipe e referências

**Equipe Berkanan** — UnB, *Tópicos Especiais em Engenharia de Software: Sistemas de Machine Learning* (2026/02).

### Papéis (modelo Kreuzberger, Kühl e Hirschl, *IEEE Access*, 2023)

| Integrante | Papéis | Responsabilidades no projeto |
|---|---|---|
| **João Victor** | **R1** Stakeholder + **R2** Arquiteto | Essential Question e escopo; ADRs (001 a 008); coordenador por regras (LangGraph), agente de comparação e verificação por regras (Config. B) |
| **Gustavo (Líder)** | **R3** Cientista de Dados | Conjunto de teste (50 perguntas + ~30 fotos) e gabarito; benchmarks (LLM vs RAG, verificador A/B/C, extração OCR); avaliação com usuários e métricas |
| **Davi Rodrigues** | **R4** Engenheiro de Dados | Fontes oficiais; ingestão no ChromaDB (`base_conhecimento_v1`); migrações PostgreSQL, TACO, limites IN 75, cache e `metricas_requisicao`; regras de extração do OCR |
| **Carlos** | **R5** Engenheiro de Software | API FastAPI; agente nutricional e verificador com LLM (Config. C); integração do OCR à API; aplicação web Mobile First (React + Vite + Tailwind) |
| **Caio Soares de Andrade** | **R6** DevOps + **R7** MLOps | Estrutura do repositório, preservação de baselines, Docker Compose, ambientes, CI/CD (GitHub Actions); versionamento de prompts, índices e configurações; deploy e monitoramento |

### Fontes oficiais previstas na base de conhecimento

> **`PENDENTE`:** a lista foi montada de memória; versões e links ainda precisam ser conferidos ao baixar (R4). No banco, as 5 fontes viram 6 registros em `fontes_documentos` (RDC 429 e IN 75 separadas, porque os limites vêm da IN 75), todos `pendente_conferencia` em 14/11.

- **Ministério da Saúde:** *Guia Alimentar para a População Brasileira* (2ª ed., 2014) — ChromaDB (RAG)
- **ANVISA:** *RDC nº 429/2020* e *Instrução Normativa — IN nº 75/2020* (rotulagem nutricional e frontal "ALTO EM") — ChromaDB (texto) e PostgreSQL (limites numéricos)
- **NEPA / Unicamp:** *Tabela Brasileira de Composição de Alimentos (TACO)* — PostgreSQL
- **Organização Mundial da Saúde (OMS):** Diretrizes sobre ingestão de açúcares e sódio — ChromaDB (RAG)
- **Sociedade Brasileira de Diabetes (SBD):** Diretrizes e orientações nutricionais reaproveitadas do Desafio 1 — ChromaDB (RAG)

### Referências técnicas e acadêmicas
- Kreuzberger, D., Kühl, N., & Hirschl, S. (2023). *Machine Learning Operations (MLOps): Overview, Definition, and Architecture*. IEEE Access.
- Documentação oficial: [FastAPI](https://fastapi.tiangolo.com/) · [LangGraph](https://langchain-ai.github.io/langgraph/) · [PostgreSQL](https://www.postgresql.org/docs/) · [ChromaDB](https://docs.trychroma.com/) · [Docker](https://docs.docker.com/)

---

## Licença

Projeto acadêmico. Uso educacional.

> **Aviso final:** este sistema é uma prova de conceito acadêmica de apoio informativo à leitura de rótulos. Ele **não substitui** avaliação de médico ou nutricionista e **nunca garante ausência de alergênicos** sem conferência direta na embalagem do produto.
