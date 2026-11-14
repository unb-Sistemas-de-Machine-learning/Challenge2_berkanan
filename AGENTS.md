# AGENTS.md — Guia de Governança para Agentes de Desenvolvimento (Challenge 2 Berkanan)

Este repositório pertence à **Equipe Berkanan** (UnB — *Tópicos Especiais em Engenharia de Software: Sistemas de Machine Learning*, 2026/02).

Qualquer agente de IA (Claude Code, Antigravity, Codex, Copilot, Cursor, etc.) ou desenvolvedor que atue neste repositório **DEVE** seguir rigorosamente as diretrizes abaixo antes de modificar código, infraestrutura ou documentação.

---

## 1. Leitura Obrigatória Antes de Qualquer Alteração

Antes de propor ou executar mudanças arquiteturais, de dados ou de código, consulte obrigatoriamente:

1. **Índice consolidado de contexto:** [docs/context/INDEX.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/INDEX.md)
2. **Manifesto de documentos e ADRs:** [docs/context/MANIFEST.yaml](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/MANIFEST.yaml)
3. **Fontes documentais originais (imutáveis):**
   - [docs/context/sources/contextoCLAUDEV2.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/sources/contextoCLAUDEV2.md)
   - [docs/context/sources/adr.pdf](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/sources/adr.pdf) (ADR-001 a ADR-008)
   - [docs/context/sources/5_perguntas_escopo_essential_question.pdf](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/sources/5_perguntas_escopo_essential_question.pdf)
4. **Estado do baseline do backend:** [docs/baselines/backend-whatsapp-v0.1.0.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/baselines/backend-whatsapp-v0.1.0.md) e [snapshots/backend/whatsapp-v0.1.0/manifest.yaml](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/snapshots/backend/whatsapp-v0.1.0/manifest.yaml)
5. **Divisão de responsabilidades e handoff:** [docs/handoff/RESPONSIBILITIES.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/handoff/RESPONSIBILITIES.md)
6. **Manifesto de execução MLOps:** [mlops/manifests/runtime-manifest.yaml](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/mlops/manifests/runtime-manifest.yaml)

---

## 2. Preservação das Decisões Aprovadas (ADRs)

Não contradiga nem substitua decisões marcadas como **APROVADO** sem validação explícita do líder (**Gustavo — R3**) e do arquiteto (**João Victor — R2**):

- **ADR-001 (Armazenamento híbrido):** PostgreSQL para dados estruturados (TACO, limites IN 75, cache de produtos, métricas) + ChromaDB para textos de fontes oficiais (RAG).
- **ADR-002 (Extração de rótulos):** Compressão da foto no navegador mobile (~1280 px, JPEG, ≤ 300 KB) → OpenCV no servidor → OCR tradicional em CPU (Tesseract ou PaddleOCR, sujeito a benchmark) → Regras determinísticas e validação de consistência → **Confirmação obrigatória pelo usuário** (LLM multimodal apenas como reserva em caso de falha).
- **ADR-003 (Backend central):** FastAPI no servidor centralizando a orquestração; nenhum processamento pesado roda no celular.
- **ADR-004 (Orquestração):** LangGraph com **coordenador determinístico baseado em regras** (sem chamada ao LLM para roteamento) e limite máximo de **1 a 2 chamadas ao LLM por resposta**.
- **ADR-005 (Verificação):** Três configurações em benchmark (A: sem verificador; B: regras determinísticas; C: verificador com LLM). A Configuração C só é adotada se obtiver **≥ +5 pontos percentuais de fidelidade** sobre B com **≤ +3 segundos de latência adicional**. O verificador deve ser configurável (`enable_verifier`).
- **ADR-006 (Versionamento MLOps):** Controle de versões de modelos externos, prompts, configurações de inferência e índices vetoriais (`base_conhecimento_v1`, `v2`...) via Git e manifestos estruturados.
- **ADR-007 (CI/CD):** GitHub Actions validando sintaxe, dependências, containers e smoke tests a cada push/PR.
- **ADR-008 (Monitoramento):** Logs + tabela `metricas_requisicao` no PostgreSQL (uma linha por requisição). **Não utilizar Prometheus.** Grafana é opcional apenas na semana 5.

---

## 3. Regras Inegociáveis de Segurança, Domínio e Escopo

1. **Zero cálculo ou invenção numérica pelo LLM:** Todo valor nutricional vem do PostgreSQL ou do rótulo confirmado pelo usuário, processado via SQL/código determinístico. O LLM apenas explica.
2. **Citação obrigatória de evidências:** Toda resposta deve citar a fonte oficial recuperada via RAG. Quando não houver cobertura na base ou no rótulo, responder explicitamente: `"não há evidência suficiente"`.
3. **Alergênicos:** Ler a seção `"ALÉRGICOS"` do rótulo, mas **nunca afirmar que um produto é "livre de alergênicos"**. Exibir sempre aviso para o usuário conferir a embalagem física.
4. **Aviso médico/nutricional fixo:** O sistema possui caráter informativo e não realiza diagnóstico, prescrição de dieta, recomendação de doses de medicamentos ou planos alimentares individualizados.
5. **Privacidade e LGPD:** Não armazenar fotografias de rótulos nem perfis pessoais de saúde em bancos de dados ou arquivos de log sem consentimento explícito.
6. **Não criar funcionalidades fora do escopo:** Não implementar apps nativos Android/iOS, PWA, OCR no cliente, leitura de código de barras / Open Food Facts ou detecção de símbolo de transgênicos sem aprovação.

---

## 4. Respeito à Divisão de Papéis (R1 a R7)

Atue estritamente dentro do papel solicitado na tarefa:

- **R1 / R2 (João Victor):** Escopo, Essential Question, ADRs, coordenador por regras, agente de comparação, verificação por regras (Config. B).
- **R3 (Gustavo — Líder):** Conjunto de teste, gabaritos, execução de benchmarks (RAG vs LLM, Verificador A/B/C, OCR) e métricas.
- **R4 (Davi Rodrigues):** Fontes oficiais, migrações e carga do PostgreSQL (TACO, limites IN 75, `metricas_requisicao`), ingestão ChromaDB (`base_conhecimento_v1`), regras de extração OCR.
- **R5 (Carlos):** API FastAPI, agente nutricional, verificador com LLM (Config. C), integração do OCR à API, frontend web Mobile First.
- **R6 / R7 (Caio Soares de Andrade):** Estrutura do repositório, preservação de baselines, Docker/Docker Compose, CI/CD, versionamento de prompts/índices/configurações e infraestrutura de monitoramento.

---

## 5. Rigor Técnico, Testes e Proibições para Agentes

- **Diferencie com precisão:**
  - `APROVADO`: decisão formalmente validada pela equipe.
  - `PENDENTE`: etapa ou decisão ainda não concluída.
  - `PROPOSTO`: sugestão técnica que aguarda validação.
  - `IMPLEMENTADO`: funcionalidade existente e verificada em código executável.
  - `SIMULADO`: código esqueleto/mock (como os dados fixos atuais em `backend/graph.py`).
- **Integridade do Snapshot:** Nunca modifique nem remova os arquivos em `snapshots/backend/whatsapp-v0.1.0/` ou em `docs/context/sources/`. Execute `python3 scripts/verify_baseline.py` para validar hashes SHA-256.
- **Proibição de dados ou benchmarks inventados:** Nunca invente resultados de benchmark, métricas de acurácia/latência, versões de modelos não testadas ou limites normativos da ANVISA de memória.
- **Infraestrutura enxuta:** Não instale serviços adicionais (Prometheus, MLflow, Redis, filas pesadas, bancos extras) nem bibliotecas pesadas de OCR no container antes da definição experimental.
- **Evidência de testes e commits:** Sempre execute os scripts de verificação (`python3 scripts/verify_baseline.py` e `bash scripts/smoke_backend.sh`) e faça commits pequenos, atômicos e com mensagens claras (avaliação individual por commits).
