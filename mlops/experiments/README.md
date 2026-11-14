# Rastreabilidade de Índices Vetoriais e Experimentos (C6 / C7)

> **Responsáveis:** **Caio Soares de Andrade (R7 — MLOps)** pela estrutura de rastreabilidade; **Davi Rodrigues (R4 — Dados)** pela ingestão dos documentos e criação dos índices; **Gustavo (R3 — Cientista de Dados)** pela condução dos experimentos e benchmarks.

---

## 1. Versionamento de Índices ChromaDB (ADR-006)

A ingestão dos documentos oficiais (Guia Alimentar, RDC 429/2020, IN 75/2020, OMS e SBD) e a criação efetiva das coleções no ChromaDB são de responsabilidade de **R4 (Engenheiro de Dados)**.

### 1.1 Padrão de Nomenclatura Aprovado
As coleções no ChromaDB devem utilizar identificadores versionados sequenciais:
- `base_conhecimento_v1`
- `base_conhecimento_v2`
- `base_conhecimento_vN`

### 1.2 Quando criar uma nova versão de índice (`vN` → `vN+1`)
Uma nova versão da coleção deve ser gerada sempre que houver alteração em qualquer um dos seguintes fatores:
1. Inclusão, substituição ou atualização de documentos oficiais na tabela `fontes_documentos`;
2. Alteração nos parâmetros de segmentação (*chunk size* inicial de `1000` caracteres ou *overlap* inicial de `150` caracteres);
3. Troca do modelo de embeddings do HuggingFace;
4. Alteração na limpeza ou normalização textual pré-indexação.

### 1.3 Metadados Obrigatórios por Trecho (Chunk)
Para viabilizar a citação obrigatória de fontes (Regra 4) e a auditoria de experimentos, cada chunk indexado no ChromaDB deve conter:
- `documento`: nome canônico da fonte (ex.: `"Guia Alimentar para a População Brasileira"`, `"IN 75/2020"`);
- `fonte_id`: referência ao registro correspondente em `fontes_documentos`;
- `arquivo`: nome do arquivo original processado;
- `pagina`: número da página ou seção de origem;
- `versao_indice`: identificador da coleção (ex.: `"base_conhecimento_v1"`).

---

## 2. Registro de Experimentos e Benchmarks (C7 — Metadata Store)

O projeto prevê três baterias principais de experimentos conduzidas por **R3 (Gustavo)**:

1. **Benchmark 1 — LLM Puro vs. RAG (Semana 2):**
   - Meta: Acerto do RAG ≥ 15 pontos percentuais acima do LLM puro; Fidelidade ≥ 90%; Recall@3 ≥ 80%; Recusa correta fora do escopo ≥ 90%.
2. **Benchmark 2 — Estratégia de Verificação A vs. B vs. C (Semana 3 — ADR-005):**
   - Mesmo conjunto de teste (~50 perguntas + ~30 rótulos), mesmo modelo, `temperature = 0`, 3 repetições.
   - **Config. A:** Sem verificador (`enable_verifier: false`).
   - **Config. B:** Verificação determinística por regras em código (sem chamada ao LLM).
   - **Config. C:** Agente verificador com LLM.
   - **Regra de decisão aprovada:** A Config. C só é adotada se apresentar **ganho ≥ 5 pontos percentuais em fidelidade** sobre B e **aumento de latência ≤ 3 segundos** sobre B.
3. **Benchmark 3 — Extração de Rótulos por OCR (Semana 4 — ADR-002):**
   - Comparativo entre **Tesseract** e **PaddleOCR** (e acionamento da reserva multimodal) em ~30 fotografias reais de rótulos.
   - Meta: Acerto na extração dos campos nutricionais ≥ 85%.

### 2.1 Como registrar uma execução experimental
Cada execução oficial de benchmark deve vincular seus resultados ao estado exato registrado em [mlops/manifests/runtime-manifest.yaml](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/mlops/manifests/runtime-manifest.yaml) e na tabela `metricas_requisicao` do PostgreSQL, informando no mínimo:
- `experiment_id` e data/hora UTC;
- Hash do commit Git (`git rev-parse HEAD`);
- Nome e versão do modelo de linguagem e do modelo de embeddings;
- Versão dos prompts (`mlops/prompts/`);
- Versão do índice ChromaDB (`base_conhecimento_v1`, etc.);
- Configuração avaliada (`A`, `B` ou `C` / motor OCR).

> [!CAUTION]
> **Proibição de Dados Simulados como Resultado Experimental:** Nenhum resultado obtido com o backend ainda em modo mock (`backend-whatsapp-v0.1.0`) pode ser registrado como evidência de benchmark dos modelos ou do verificador.
