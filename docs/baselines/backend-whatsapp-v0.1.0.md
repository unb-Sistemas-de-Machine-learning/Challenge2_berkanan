# Baseline do Backend — `backend-whatsapp-v0.1.0`

## 1. Identificação e Rastreabilidade

| Campo | Valor |
|---|---|
| **Identificador do Baseline** | `backend-whatsapp-v0.1.0` |
| **Data de captura** | 14/11/2026 |
| **Timestamps originais dos arquivos** | 13/11/2026 (18:21 a 19:11 BRT) |
| **Origem** | Entrega compartilhada via WhatsApp pela equipe de Backend (`backend.zip`) |
| **Responsáveis pelo código (Backend)** | Carlos (R5 — Eng. de Software) e João Victor (R2 — Arquiteto) |
| **Responsável pela preservação** | Caio Soares de Andrade (R6 — DevOps / R7 — MLOps) |
| **Commit Git do Baseline** | `28a8fa27516b77de81a5585f8aed4f0397f5a888` |
| **Snapshot imutável** | [snapshots/backend/whatsapp-v0.1.0/original/](../../snapshots/backend/whatsapp-v0.1.0/original) |
| **Manifesto técnico** | [manifest.yaml](../../snapshots/backend/whatsapp-v0.1.0/manifest.yaml) |
| **Hashes SHA-256** | [SHA256SUMS](../../snapshots/backend/whatsapp-v0.1.0/SHA256SUMS) |
| **Localização canônica executável** | [backend/](../../backend) |

---

## 2. O que o Backend já implementou neste Baseline (`IMPLEMENTADO`)

1. **Aplicação FastAPI ([backend/main.py](../../backend/main.py)):**
   - Instância FastAPI exportada como `api` (`title="Berkanan Desafio 2 - API Local"`).
   - Endpoint `POST /api/analyze` recebendo `AnalysisRequest` e retornando `AnalysisResponse`.
   - Medição de tempo de execução em milissegundos (`response_time_ms`) via `time.perf_counter()`.
   - Preenchimento opcional do objeto `verification` (`VerificationResult`) quando `request.enable_verifier == True`.
2. **Orquestração inicial com LangGraph ([backend/graph.py](../../backend/graph.py)):**
   - Grafo de estado (`StateGraph(AgentState)`) compilado como `app`.
   - Três nós declarados: `coordinator`, `nutritional` e `verifier`.
   - Transição condicional `route_verifier` após o nó `nutritional`, desviando para `verifier` quando `enable_verifier=True` ou encerrando em `END` quando `enable_verifier=False`.
3. **Contratos de Dados ([backend/schemas.py](../../backend/schemas.py) e [backend/state.py](../../backend/state.py)):**
   - Tipos literais `RequestType` (`"ocr_analysis"`, `"comparison"`, `"qa"`) e `RecommendationTone` (`"SAUDAVEL"`, `"ATENCAO"`, `"EVITAR"`, `"INCONCLUSIVO"`, `"ERRO"`).
   - Modelos Pydantic: `UserProfile`, `AnalysisRequest`, `MatchedSource`, `ExtractedOCRData`, `VerificationResult`, `AnalysisResponse`.
   - Estado tipado `AgentState` (`TypedDict`) para trânsito de dados no grafo.
4. **Script básico de teste manual ([backend/test_api.sh](../../backend/test_api.sh)):**
   - Duas chamadas `curl` exercitando `enable_verifier: true` e `enable_verifier: false`.

---

## 3. O que permanece simulado ou pendente (`PENDENTE` / `SIMULADO`)

- **Coordenador (`coordinator_node`):** Atualmente apenas imprime log e retorna `{}` sem rotear dinamicamente entre análise de rótulo, dúvidas gerais (`qa`) ou comparação de dois produtos (`comparison`).
- **Agente Nutricional (`nutritional_agent_node`):** Retorna valores fixos simulados (`draft_response`, `matched_sources` apontando para `guia_alimentar_pag_45.pdf`, aviso fixo para diabéticos e tom `EVITAR`).
- **Agente de Comparação:** Ainda não implementado no grafo.
- **Agente Verificador (`verifier_agent_node`):** Apenas verifica se `bool(state.get("matched_sources"))` é verdadeiro. Ainda não implementa a verificação determinística completa por regras (Configuração B do ADR-005) nem a verificação semântica com LLM (Configuração C do ADR-005).
- **Integração com Bancos de Dados (ADR-001):** Não há conexão com PostgreSQL (TACO, limites da IN 75, cache de produtos, tabela `metricas_requisicao`) nem com ChromaDB (recuperação RAG).
- **Pipeline de Imagem e OCR (ADR-002):** O campo `image_base64` existe no contrato, mas não há pré-processamento OpenCV, extração OCR (Tesseract/PaddleOCR), validação matemática nem etapa de confirmação pelo usuário.

---

## 4. O que foi reorganizado por R6/R7 (Infraestrutura e MLOps)

Nenhuma linha de código funcional ou regra de negócio dos arquivos do backend foi alterada. As ações realizadas por **Caio Soares de Andrade (R6/R7)** restringiram-se a:

1. **Preservação imutável:** Cópia integral byte a byte dos 7 arquivos originais para `snapshots/backend/whatsapp-v0.1.0/original/` (incluindo `README(1).md`) com geração de `SHA256SUMS` e `manifest.yaml`.
2. **Movimentação rastreável no Git (`git mv`):** Organização dos 7 arquivos na pasta canônica `backend/` (renomeando `README(1).md` para `backend/README.md`).
3. **Containerização externa ao código:** Adição de `backend/Dockerfile` e `compose.yaml` executando `uvicorn main:api --host 0.0.0.0 --port 8000` sem alterar `main.py`.
4. **Automação de testes e CI:** Criação de `scripts/verify_baseline.py` e `scripts/smoke_backend.sh` (sem sobrescrever `backend/test_api.sh`) e pipeline `.github/workflows/ci.yml`.

---

## 5. Classificação obrigatória para mudanças futuras

Para preservar a rastreabilidade acadêmica e arquitetural do projeto, toda alteração subsequente ao baseline `backend-whatsapp-v0.1.0` deve ser explicitamente classificada nos commits e Pull Requests em uma das cinco categorias abaixo:

1. **Evolução funcional do backend (R2/R4/R5):** Implementação real dos nós do LangGraph, integração com PostgreSQL/ChromaDB, pipeline OpenCV/OCR, regras de validação ou novos endpoints FastAPI.
2. **Mudança de infraestrutura (R6):** Alterações em `Dockerfile`, `compose.yaml`, scripts de provisionamento, redes, volumes ou workflows do GitHub Actions (`.github/workflows/`).
3. **Mudança de configuração (R6/R7):** Ajustes em variáveis de ambiente (`.env.example`), portas, timeouts ou parâmetros de inicialização.
4. **Mudança de dependências (R4/R5/R6):** Adição ou atualização de pacotes em `backend/requirements.txt` ou dependências de sistema no container.
5. **Mudança experimental de MLOps (R3/R7):** Atualizações em `mlops/manifests/runtime-manifest.yaml`, novas versões de prompts em `mlops/prompts/`, registro de versões de índices vetoriais (`base_conhecimento_vN`) ou consultas de monitoramento em `mlops/monitoring/`.

> [!IMPORTANT]
> Reorganizações de diretórios, ajustes de Docker ou criação de manifestos nunca devem ser descritos como evolução funcional dos agentes.
