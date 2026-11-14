# Monitoramento e Observabilidade — Challenge 2 Berkanan (ADR-008 / C9)

> **Status da decisão:** `APROVADO` em 13/11/2026 (João Victor, Caio e Gustavo).  
> **Status da implementação em código (14/11/2026):** Infraestrutura PostgreSQL pronta em `compose.yaml`; migração `004_metricas.sql` revisada por R4 (aguardando inclusão no repositório); instrumentação no `backend/` `PENDENTE`.

---

## 1. Decisão Arquitetural (ADR-008)

1. **Armazenamento de métricas no PostgreSQL:** Utilizar logs estruturados da aplicação e a tabela dedicada `metricas_requisicao` no PostgreSQL (uma linha por requisição processada).
2. **Proibição do Prometheus:** **Não utilizar Prometheus** na arquitetura do projeto, evitando adicionar um serviço extra de coleta de séries temporais.
3. **Alertas e análise:** Sem alertas automáticos na primeira entrega; a verificação de limiares e agregações é feita por consultas SQL e pelas views `vw_*` criadas nas migrações do banco.
4. **Grafana opcional:** O uso do Grafana (conectado diretamente ao PostgreSQL) é opcional e só deverá ser avaliado na **Semana 5** caso haja tempo e necessidade.

---

## 2. O que é Monitorado e Metas / Limiares (Gatilhos)

Conforme definido em `5_perguntas_escopo_essential_question.pdf` (Questões 4 e 5) e no `ADR-008`:

| Indicador Monitorado | Limiar / Meta | Gatilho de Ação |
|---|---|---|
| **Acerto da extração (OCR)** | **≥ 85%** dos campos extraídos corretamente | Se `< 85%`: disparar investigação nas regras de pré-processamento OpenCV / OCR |
| **Fidelidade às fontes (RAG)** | **≥ 90%** das afirmações sustentadas pelas fontes | Se `< 90%`: revisar chunking, reindexar ChromaDB (`base_conhecimento_vN+1`) ou ajustar prompts/verificador |
| **Latência total de resposta** | Mediana **≤ 10 s** em rede móvel 4G | Se `> 10 s`: investigar gargalos por etapa (OCR, RAG, chamadas LLM, container) |
| **Chamadas ao LLM por resposta** | Média **≤ 2** chamadas por requisição | Verificar se o coordenador continua determinístico e se o verificador/fallback não excedem o limite |
| **Falhas de leitura e erros HTTP/Serviços** | Monitoramento contínuo por requisição | Identificar falhas de conexão com PostgreSQL/ChromaDB ou timeouts da API do LLM |

---

## 3. Destinação do Feedback Operacional (Roteamento por Papel)

Quando as consultas SQL em `metricas_requisicao` ou os logs indicarem desvios, o feedback é direcionado conforme aprovado no ADR-008:

- **Falhas de leitura do rótulo e extração de nutrientes → Davi Rodrigues (R4):** revisão das regras de extração, normalização por 100 g e checagens de consistência.
- **Queda de fidelidade, recall ou qualidade das respostas → Gustavo (R3):** revisão dos experimentos, conjuntos de teste, gabaritos e parâmetros de recuperação RAG.
- **Problemas de latência, containers, CI/CD e infraestrutura → Caio Soares de Andrade (R6/R7):** investigação de gargalos de recursos, rede, banco e configurações de execução.
- **Erros de integração da API, fluxo LangGraph e UI mobile → Carlos (R5):** correções nos endpoints FastAPI, integração dos agentes e aplicação React.
- **Necessidade de mudança estrutural ou revisão de tecnologia → João Victor (R2):** avaliação de impacto arquitetural e criação/atualização de ADRs.

---

## 4. Proteção de Dados e LGPD no Monitoramento

- A tabela `metricas_requisicao` e os logs de execução **não devem armazenar fotografias (`image_base64`) nem dados pessoais identificáveis ou condições de saúde vinculadas ao indivíduo**.
- O registro de métricas deve ser resiliente (falhas ao gravar uma métrica não devem derrubar a resposta principal ao usuário).
