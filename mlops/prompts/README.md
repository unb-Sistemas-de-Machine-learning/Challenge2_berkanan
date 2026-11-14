# Versionamento de Prompts — Challenge 2 Berkanan (R7)

> **Status atual (14/11/2026):** Estrutura preparada por **R7 (Caio Soares de Andrade)**. Nenhum prompt nutricional foi criado nesta etapa em respeito à divisão de papéis (**R2 — João Victor**, **R3 — Gustavo** e **R5 — Carlos**).

---

## 1. Contexto Arquitetural (ADR-004 e ADR-006)

Como o Berkanan utiliza modelos de linguagem existentes sem treinamento de pesos próprios, o componente **C6 — Model Registry** é adaptado para controlar rigorosamente:
1. Versão do modelo de linguagem e parâmetros de inferência;
2. **Versão exata dos prompts dos agentes**;
3. Versão do índice vetorial no ChromaDB (`base_conhecimento_v1`, `v2`...).

Importante (ADR-004):
- O **Coordenador** roteia requisições exclusivamente por **regras determinísticas em código** e **não utiliza prompt de LLM**.
- Os agentes que utilizam prompt quando integrados ao LLM são:
  - **Agente Nutricional** (`nutritional_agent`)
  - **Agente de Comparação** (`comparison_agent`)
  - **Agente Verificador — Configuração C** (`verifier_agent_llm`)
  - **Extrator Multimodal de Reserva** (`ocr_vision_fallback`)

---

## 2. Convenção de Nomenclatura e Versionamento

Quando os responsáveis pelos agentes (R2/R5) adicionarem os prompts reais a este diretório, deverão seguir o padrão:

```text
mlops/prompts/<nome_do_agente>_v<MAJOR>.<MINOR>.yaml
```

Exemplos:
- `mlops/prompts/nutritional_agent_v1.0.yaml`
- `mlops/prompts/comparison_agent_v1.0.yaml`
- `mlops/prompts/verifier_agent_llm_v1.0.yaml`

### Regras de incremento de versão
- **Incremento `MAJOR` (`v1.0` → `v2.0`):** Mudança estrutural nas instruções de sistema, alteração nas regras de formato de saída/citação ou mudança de escopo.
- **Incremento `MINOR` (`v1.0` → `v1.1`):** Ajustes de redação ou exemplos (*few-shot*) mantendo o mesmo contrato de saída.
- **Imutabilidade para Benchmarks:** Uma vez que uma versão (ex.: `v1.0`) tenha sido utilizada em um benchmark oficial de R3, o arquivo não deve ser sobrescrito; crie uma nova versão (`v1.1` ou `v2.0`) e atualize [mlops/manifests/runtime-manifest.yaml](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/mlops/manifests/runtime-manifest.yaml).

---

## 3. Template de Metadados de Prompt

Cada arquivo de prompt versionado neste diretório deverá conter o seguinte cabeçalho YAML:

```yaml
prompt_id: "nutritional_agent"
version: "v1.0"
status: "PROPOSTO" # PROPOSTO | EM_BENCHMARK | APROVADO | OBSOLETO
owner_role: "R5"
created_at: "YYYY-MM-DD"
compatible_models:
  - "gemini-*"
system_constraints_enforced:
  - "Proibido calcular ou inventar numeros nutricionais (usar apenas valores vindos do PostgreSQL/rotulo confirmado)"
  - "Citacao obrigatoria dos trechos recuperados do ChromaDB"
  - "Responder 'nao ha evidencia suficiente' quando a base nao cobrir a pergunta"
  - "Nunca afirmar que o produto e livre de alergenicos; exigir conferencia na embalagem"
  - "Incluir aviso fixo de que nao substitui orientacao medica ou nutricional"
template: |
  <inserir instrucoes aprovadas pelo responsavel do agente>
```
