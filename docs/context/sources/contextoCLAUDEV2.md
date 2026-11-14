# Desafio 2 — Contexto do projeto para o Claude Code

> Base de conhecimento da Equipe Berkanan (UnB, Tópicos Especiais em Engenharia de Software: Sistemas de Machine Learning, 2026/02).
> Atualizado em 14/11/2026. Salve na raiz do repositório como `CLAUDE.md` para o Claude Code ler automaticamente.
> Seções marcadas como **APROVADO** são decisões do grupo; **PENDENTE** ainda não foi decidido ou entregue. Não altere decisões aprovadas sem confirmação do líder (Gustavo).

---

## 1. O desafio

- **Big Idea:** "Empoderando pessoas com IA para compreender melhor, decidir melhor e viver melhor" (tema: Qualidade de Vida).
- **Challenge Statement:** projetar e desenvolver uma solução baseada em IA que apoie a tomada de decisão em um contexto de qualidade de vida.
- **Restrições do professor (obrigatórias em todo o trabalho):**
  1. Entender o problema antes da solução
  2. Justificar decisões técnicas
  3. Explicitar riscos e limitações
  4. Validar com métricas objetivas
  5. Utilizar evidências confiáveis
- **Entrega final:** 07/12/2026 (aplicação, relatório e apresentação).
- **Avaliação individual:** o professor avalia cada aluno pela quantidade e relevância dos commits. Commits pequenos, frequentes e com mensagem clara.

## 2. Problema e Essential Question (APROVADO)

**Problema:** as pessoas decidem o que comprar com base em rótulos nutricionais difíceis de ler, em marketing e em redes sociais. A informação confiável existe (Guia Alimentar, ANVISA), mas está em documentos longos que ninguém consulta na hora da compra.

**Essential Question:** Como a inteligência artificial pode usar os rótulos de produtos e fontes oficiais para ajudar a orientar os consumidores brasileiros a escolher opções mais saudáveis na sua alimentação de forma rápida e confiável?

**Público:** consumidor adulto no supermercado, usando o celular. Grupo de maior risco: pessoas com diabetes ou hipertensão.

## 3. Escopo (APROVADO em 05/11 e 12/11)

**O sistema faz:**
- Lê a foto do rótulo e explica o produto: açúcar, sódio, gordura saturada, %VD (percentual de valores diários) e grau de processamento.
- Avisa se o produto contém alergênicos (ex.: lactose, glúten), lendo a linha "ALÉRGICOS" do rótulo, sempre com aviso para conferir na embalagem.
- Compara dois produtos e indica o mais adequado, citando a fonte.
- Responde dúvidas sobre alimentação com base nas fontes oficiais.
- Emite avisos para quem informa ter diabetes ou hipertensão.
- Responde "não há evidência suficiente" quando a base ou o rótulo não cobrem a pergunta.

**O sistema NÃO faz:**
- Diagnóstico, prescrição de dieta ou doses de medicamento.
- Planos alimentares individualizados (encaminha a um nutricionista).
- Recomendação de marcas ou produtos comerciais.

**Fora do escopo por enquanto** (só reavaliar com o trabalho 100% pronto):
- Transgênicos (dependem de reconhecer o símbolo "T" na imagem).
- Leitura de código de barras / Open Food Facts.
- Atividade física (tema descartado em 05/11).

## 4. Regras que o código deve respeitar (APROVADO)

1. **App leve para navegador de celular.** O celular só captura a foto e exibe o resultado; todo processamento pesado roda no servidor.
2. **Imagem comprimida no navegador** antes do envio (~1280 px, JPEG, até ~300 KB).
3. **Todo número vem da base estruturada (PostgreSQL) via SQL/código.** O LLM só explica; nunca calcula nem inventa valores.
4. **Toda resposta cita a fonte** (trecho recuperado do RAG). Sem evidência → responder "não há evidência suficiente".
5. **No máximo 1 ou 2 chamadas ao LLM por resposta.** O coordenador roteia por regras, sem chamar o LLM.
6. **Nunca afirmar que um produto é livre de alergênicos.** Sempre mostrar aviso para conferir a embalagem.
7. **O usuário confirma os valores lidos** do rótulo antes da análise.
8. **Aviso fixo:** o sistema não substitui orientação médica ou nutricional.
9. **LGPD:** não armazenar fotos nem perfil de saúde sem consentimento.
10. **Modelo alternativo configurado** caso a cota gratuita do Gemini acabe.
11. **Toda decisão técnica relevante vira um ADR** no repositório (exigência do material do professor).

## 5. Arquitetura (APROVADA em 11/11, após feedback do professor)

### 5.1 Fluxo

```
EXTRAÇÃO DO RÓTULO
Foto no celular (comprimida) → [servidor] OpenCV (cinza, inclinação, binarização)
  → OCR (Tesseract ou PaddleOCR) → Regras + validação (campos da RDC 429)
  → (falhou?) LLM com visão como reserva, ou pedir correção ao usuário
  → Usuário confirma os valores

ANÁLISE
Coordenador (roteia por regras: foto, pergunta ou comparação)
  → Agente nutricional / Agente de comparação
       ↳ PostgreSQL: TACO, limites da rotulagem, cache (números)
       ↳ ChromaDB: textos das fontes (RAG, explicações com citação)
  → Verificação (por regras ou com LLM, decidido por benchmark)
  → Resposta com fontes
```

### 5.2 Extração de dados: OCR + regras, LLM só como reserva

A tabela nutricional segue formato padronizado pela ANVISA (RDC 429/2020 e IN 75/2020): mesmos nomes de campos, valores por 100 g e por porção.

1. **Celular:** recorta e reduz a foto antes de enviar.
2. **Pré-processamento:** OpenCV (escala de cinza, correção de inclinação, binarização).
3. **OCR:** Tesseract (português) ou PaddleOCR, em CPU. A escolha sai do benchmark da semana 4.
4. **Regras:** expressões regulares extraem os campos (valor energético, carboidratos, açúcares totais e adicionados, proteínas, gorduras totais, saturadas e trans, fibra, sódio, %VD) e a linha "ALÉRGICOS"; normalizam para 100 g.
5. **Validação de consistência:** ex.: açúcares ≤ carboidratos; energia ≈ 4×carboidratos + 4×proteínas + 9×gorduras. Se falhar ou faltar campo → LLM com visão só nessa foto, ou pedir correção ao usuário.
6. **Confirmação:** o usuário confere os valores.

### 5.3 Duas bases de dados

| Base | Tecnologia | Conteúdo | Uso |
|---|---|---|---|
| Vetorial | ChromaDB | Textos do Guia Alimentar, normas da ANVISA, OMS, SBD | Explicar e justificar com citação (RAG) |
| Estruturada | PostgreSQL | TACO, limites da rotulagem frontal da ANVISA, cache de produtos lidos | Cálculos exatos: "alto em", comparação, conversão por 100 g |

### 5.4 Agente verificador: decidido por benchmark

Mesmo conjunto de teste (~50 perguntas + ~30 rótulos), mesmo modelo, temperatura 0, 3 repetições:

| Config. | Verificação |
|---|---|
| A | Sem verificador |
| B | Por regras, sem LLM: todo número existe na base estruturada e toda resposta cita um trecho recuperado |
| C | Agente verificador com LLM |

**Regra aprovada:** o verificador com LLM (C) só fica se aumentar a fidelidade em ≥ 5 pontos sobre B, sem somar mais de 3 s à resposta. Caso contrário, fica a verificação por regras (B).
O verificador precisa ser **ligável/desligável por configuração**.

### 5.5 Stack

| Camada | Escolha |
|---|---|
| Frontend | React + Vite + Tailwind (app web para celular) |
| Backend | Python + FastAPI |
| Imagem | OpenCV |
| OCR | Tesseract ou PaddleOCR (benchmark) |
| Base vetorial | ChromaDB + LangChain + embeddings do HuggingFace |
| Base estruturada | PostgreSQL |
| LLM | Gemini, com modelo alternativo configurado; leitura de imagem só como reserva |
| Multiagentes | LangGraph |
| Deploy | Docker Compose |

### 5.6 CI/CD e monitoramento (APROVADO em 13/11)

O que já estava aprovado antes:
- Arquitetura leve.
- O que monitorar em produção: latência, falhas de leitura do rótulo e chamadas ao LLM por resposta (métricas aprovadas).
- CI: rodar build e testes a cada commit (tarefa do Caio, até 18/11).

**Status em 13/11:**
- **CI: APROVADO em 13/11 — GitHub Actions** (João, Caio e líder de acordo), para manter a estrutura simples sem mais uma tecnologia. Roda build e testes a cada commit.
- **Monitoramento: APROVADO em 13/11 (João, Caio e líder) — PostgreSQL**, proposto pelo João após comparar com Prometheus. Uma tabela de métricas separada no PostgreSQL, uma linha por requisição, guardando junto latência, falha de leitura, chamadas ao LLM, versão do OCR e modelo usado. Agregações e checagem do limiar (acerto < 85% ou fidelidade < 90%) por consultas SQL. Sem alertas automáticos. Grafana (lendo direto do PostgreSQL) é opcional, só na semana 5 se sobrar tempo. **Não usar Prometheus.**

### 5.7 Reaproveitamento

A stack reaproveita o Desafio 1 da equipe: https://github.com/unb-Sistemas-de-Machine-learning/challenge_1_berkanan (FastAPI, React, ChromaDB, LangChain, Gemini, PostgreSQL, Docker). O Desafio 2 é outra proposta; reaproveitar código e pipeline de ingestão, não o tema.

## 6. Base de conhecimento

| Fonte | Órgão | Base |
|---|---|---|
| Guia Alimentar para a População Brasileira (2ª ed., 2014) | Ministério da Saúde | Vetorial |
| RDC 429/2020 e IN 75/2020 (rotulagem nutricional e frontal) | ANVISA | Vetorial (texto) e estruturada (limites) |
| Tabela Brasileira de Composição de Alimentos (TACO) | NEPA/Unicamp | Estruturada |
| Diretrizes sobre açúcares e sódio | OMS | Vetorial |
| Documentos já usados no Desafio 1 | SBD | Vetorial |

**PENDENTE:** a lista foi montada de memória; versões e links precisam ser conferidos ao baixar (tarefa do Davi). No banco, as 5 fontes ficam em **6 registros** de `fontes_documentos` (RDC 429 e IN 75 separadas, porque os limites vêm da IN 75), todos ainda `pendente_conferencia` em 14/11.

### 6.1 Esquema do PostgreSQL (entregue pelo Davi em 13/11, revisado e testado em 14/11)

Arquivos: `migrations/001_fontes.sql` a `004_metricas.sql`, `migrations/migrate.sh`, `seeds/seed_exemplo.sql` (pasta `desafio2/R4_davi_corrigido/`). As migrações rodam sem erro num PostgreSQL 16 e podem ser repetidas (idempotentes).

| Tabela / view | Conteúdo |
|---|---|
| `fontes_documentos` | Fontes oficiais: versão, link, data do download, quem conferiu, `status_conferencia` (`pendente_conferencia`, `conferido`, `obsoleto`) |
| `taco_alimentos` | TACO por 100 g. `NA` e `Tr` viram `NULL`, nunca 0 |
| `limites_rotulagem` | Limites do "ALTO EM" da IN 75 por 100 g/ml (sólido/líquido × açúcares adicionados, gorduras saturadas, sódio) com o trecho literal da norma. **Vazia até copiar do texto oficial** |
| `produtos_lidos` | Cache de rótulos lidos (por 100 g/ml, porção, %VD e valores da porção em JSONB, texto da linha "ALÉRGICOS"). Nenhum campo "livre de alergênicos" |
| `metricas_requisicao` | Monitoramento aprovado em 13/11: uma linha por requisição, com colunas também para o benchmark (modo RAG/LLM puro, configuração A/B/C, categoria do teste) |
| Views `vw_*` | Agregação diária, checagem de limiares, benchmark RAG x LLM, verificador A/B/C e decisão C x B, extração OCR, categorias do teste, avaliação de usuários, painel das 10 métricas. Sem dados, mostram NULL / "Sem dados" |

Regras para quem mexer no banco:
- **Chaves para `fontes_documentos` sempre pelo nome do documento**, nunca por id fixo: `(SELECT id FROM fontes_documentos WHERE documento = 'IN 75/2020')`.
- **Único CHECK de consistência ativo:** açúcares totais ≤ carboidratos. A conta de energia (4C + 4P + 9G) é aproximada e fica no código de extração. As outras checagens sugeridas pelo Davi estão **comentadas** até o grupo aprovar.
- `migrate.sh` só aplica arquivos `NNN_*.sql`, cada um numa transação. Dados fictícios ficam em `seeds/` e só entram com `SEED=1` (dev). Senha via `PGPASSWORD`.
- Nova mudança no banco = nova migração numerada (ex.: `005_limites_in75.sql`); não editar migração já aplicada.

### 6.2 ChromaDB (PENDENTE: ainda sem textos em 14/11)

Vão para o ChromaDB: Guia Alimentar, RDC 429, IN 75, OMS e SBD (a TACO fica só no PostgreSQL). Guia e scripts em `desafio2/R4_guia/`:
- Coleções versionadas `base_conhecimento_v1`, `v2`…: mudar documento, tamanho de trecho ou modelo gera versão nova (model registry adaptado). O benchmark registra qual versão usou.
- Cada trecho guarda `documento`, `fonte_id`, `arquivo`, `pagina` e `versao_indice`, para citar a fonte (regra 4).
- Trechos de 1000 caracteres com 150 de sobreposição como ponto de partida; ajustar pelo recall top 3 (meta ≥ 80%).
- Modelo de embeddings: o mesmo do Desafio 1 (não houve decisão de trocar).

## 7. Papéis da equipe (APROVADO em 11/11)

Baseados no modelo de referência de MLOps do material do professor (Kreuzberger, Kühl e Hirschl, IEEE Access, 2023). Em equipes pequenas, uma pessoa acumula vários papéis.

| Pessoa | Papéis | Responsabilidades no projeto |
|---|---|---|
| **João Victor** | R1 Stakeholder + R2 Arquiteto | Essential Question e escopo; ADRs; **código:** coordenador por regras (LangGraph), agente de comparação, verificação por regras (config. B) |
| **Gustavo (líder)** | R3 Cientista de dados | Conjunto de teste e gabarito; benchmarks (LLM x RAG, verificador, extração); avaliação com usuários; métricas do relatório |
| **Davi Rodrigues** | R4 Eng. de dados | Fontes; ingestão no ChromaDB; TACO e limites no PostgreSQL; regras de extração do OCR e checagens; cache de produtos |
| **Carlos** | R5 Eng. de software | API FastAPI; agente nutricional e verificador com LLM; integração do OCR à API; app web para celular |
| **Caio** | R6 DevOps + R7 MLOps | Estrutura do repositório, Docker Compose, ambientes, CI/CD; versionamento de prompts, índice e configuração; deploy e monitoramento |

Relatório e apresentação: todos, cada um escreve a sua parte.

**Adaptação para LLM** (o material deixa LLMs fora do recorte): o "retreino" vira **reindexação das bases** quando entram dados novos; o "model registry" vira **versionamento de prompts, índice e configuração**.

## 8. Cronograma

| Semana | Período | Foco | Entregável |
|---|---|---|---|
| 1 | 26/10–01/11 | Problema, stakeholders, riscos, métricas | Definições do projeto |
| 2 | 02/11–08/11 | RAG e comparação LLM x RAG | Base no ChromaDB, conjunto de teste, comparação medida |
| 3 | 09/11–15/11 | Multiagentes | TACO e limites no PostgreSQL; agentes com verificador ligável; benchmark do verificador |
| 4 | 16/11–22/11 | Multimodalidade | Pipeline OCR + regras; benchmark de extração (~30 fotos) |
| 5 | 23/11–29/11 | Integração | Aplicação funcional; testes no celular (tempo e tamanho da imagem) |
| 6 | 30/11–06/12 | Testes e refinamento | Avaliação com usuários, relatório, apresentação |
| — | 07/12 | Entrega final | Aplicação, relatório e apresentação |

Feriado: 20/11. Prazos detalhados por tarefa no quadro de acompanhamento (planilha "Quadro do Desafio 2").

## 9. Métricas de validação

| Métrica | O que mede | Meta | Sem. |
|---|---|---|---|
| Acerto das respostas | % corretas frente ao gabarito | RAG ≥ 15 pontos acima do LLM puro | 2 |
| Fidelidade às fontes | % de afirmações sustentadas pelo trecho citado | ≥ 90% | 2 |
| Recall da recuperação (top 3) | % com o trecho certo entre os 3 primeiros | ≥ 80% | 2 |
| Recusa correta | % de perguntas fora da base respondidas com "sem evidência" | ≥ 90% | 2 |
| Ganho do verificador com LLM | Fidelidade e latência com e sem o agente | Fica só se ganhar ≥ 5 pontos com ≤ 3 s a mais | 3 |
| Acerto da extração | % de campos lidos corretamente das fotos | ≥ 85% | 4 |
| Custo da extração | Tempo e custo por foto por método | Comparativo Tesseract, PaddleOCR, Gemini | 4 |
| Tempo de resposta | Mediana no 4G | ≤ 10 s | 5 |
| Chamadas ao LLM | Média por resposta | ≤ 2 | 5 |
| Avaliação de usuários | Clareza e utilidade (5 a 10 pessoas) | ≥ 4 de 5 | 6 |

As metas são uma proposta inicial, a ajustar após a primeira medição.

### 9.1 Conjunto de teste (RASCUNHO, em revisão pelo Gustavo)

Arquivo: `conjunto_de_teste_rascunho.csv` (também na aba "Conjunto de teste" do quadro de acompanhamento). 50 perguntas, colunas: `ID, Categoria, Pergunta, Resposta esperada (gabarito), Fonte esperada, Comportamento esperado, Métrica, Conferir na fonte`.

| Prefixo | Categoria | Qtd. | Mede |
|---|---|---|---|
| A | Guia Alimentar | 10 | Acerto, fidelidade, recall |
| B | Rotulagem ANVISA | 10 | Acerto, fidelidade, recall |
| C | Cálculo ALTO EM (inclui normalização por porção e leitura inconsistente) | 8 | Acerto |
| D | Comparação de dois produtos | 6 | Acerto, fidelidade |
| E | Alergênicos | 5 | Acerto, segurança |
| F | Saúde e OMS (diabetes, hipertensão) | 5 | Acerto, segurança |
| G | Fora do escopo (dose, dieta, marca, transgênico, sem evidência) | 6 | Recusa correta |

O gabarito foi escrito de memória e **precisa ser conferido nas fontes oficiais** antes de valer como referência; as linhas com `Conferir na fonte = Sim` são as de menor certeza. Os produtos das categorias C e D são fictícios.

### 9.2 Benchmark do verificador (status em 14/11)

Ainda não começou. Previsto para sáb 14/11, podendo passar para qua 18/11 (líder decide conforme as respostas da equipe). As views `vw_benchmark_verificador_abc` e `vw_decisao_verificador_c_vs_b` já aplicam a regra +5 pts / ≤ 3 s. Depende das bases (Davi), do coordenador e agente de comparação (João) e do agente nutricional com verificador ligável (Carlos). Resultados devem registrar, por configuração (A/B/C): fidelidade, acerto, recusa correta, latência mediana e chamadas ao LLM por resposta.

## 10. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Alucinação sobre nutrição | Alto | Citação obrigatória; números da base estruturada; verificação; "sem evidência" |
| OCR erra (foto torta, borrada, reflexo, embalagem curva) | Alto | OpenCV; checagens de consistência; LLM com visão como reserva; confirmação do usuário |
| Usuário trata a resposta como orientação médica | Alto | Aviso fixo; triagem; encaminhamento a profissional |
| Alergênico não detectado (falso negativo) | Alto | Nunca afirmar "livre de alergênicos"; aviso para conferir a embalagem; medir acerto da linha "ALÉRGICOS" |
| Verificador não compensa custo e latência | Médio | Decidir pelo benchmark; regras como alternativa gratuita |
| App lento ou pesado no celular | Médio | Processamento no servidor; imagem comprimida; poucas chamadas ao LLM |
| Projeto parecido demais com o Desafio 1 | Médio | Foco em decisão de compra e comparação, não em checagem de fatos |
| Cota gratuita do Gemini esgota | Médio | Modelo alternativo; cache |
| Dados pessoais de saúde | Médio | Não armazenar sem consentimento (LGPD) |

## 11. Registro de decisões

| Data | Decisão |
|---|---|
| 05/11 | Tema escolhido: escolhas alimentares a partir do rótulo (atividade física descartada) |
| 11/11 | Após feedback do professor: OCR + regras com LLM só como reserva; duas bases (ChromaDB + PostgreSQL); verificador decidido por benchmark; arquitetura leve para celular |
| 11/11 | Regra do verificador: ≥ 5 pontos de fidelidade com ≤ 3 s a mais |
| 11/11 | Código de barras / Open Food Facts descartado por enquanto |
| 11/11 | Papéis R1–R7 conforme o material do professor e responsáveis definidos |
| 11/11 | João (R1+R2) também coda: coordenador, agente de comparação, verificação por regras |
| 11/11 | Repositório GitHub criado pelo professor; Caio monta a estrutura dentro dele |
| 12/11 | Essential Question do João adotada |
| 12/11 | Escopo: %VD e alergênicos entram; transgênicos ficam para depois |
| 12/11 | Feedback ao João: correções nas respostas às 5 perguntas, baseadas só no material do professor e no plano aprovado |
| 13/11 | Rascunho do conjunto de teste (50 perguntas) criado, em revisão |
| 13/11 | CI com GitHub Actions e monitoramento com PostgreSQL (Grafana opcional; Prometheus descartado), aprovados por João, Caio e líder |
| 13/11 | João entrega 8 ADRs em rascunho e a versão nova das 5 respostas; revisão com base só no plano e no material (`desafio2/revisoes/revisao_ADRs_e_5_respostas_13-11.md`) |
| 14/11 | Esquema do PostgreSQL do Davi revisado e testado: FKs por nome, seed fora de produção, só a checagem aprovada ativa, views sem dados mostram "Sem dados" (`desafio2/revisoes/revisao_R4_Davi_14-11.md`) |
| 14/11 | Guia do R4 para carregar as bases, com scripts testados (`desafio2/R4_guia/`) |

## 12. Pendências (em 14/11)

Acompanhamento detalhado: planilha "Quadro do Desafio 2" (abas Tarefas, Checkpoints do líder e Conjunto de teste).

**Repositório e organização**
- [ ] Repositório do professor liberado (ainda não criado em 14/11) → Caio monta estrutura, Docker Compose, ambientes e CI
- [ ] Configurar o GitHub Projects (líder, após acesso ao repositório)

**Davi (R4)**: atrasado; destrava João, Carlos e o benchmark
- [x] Esquema do PostgreSQL (migrações 001–004), revisado e testado em 14/11
- [ ] Baixar e conferir as 5 fontes (links, versões) e marcar `conferido` (era 12/11)
- [ ] Carregar a TACO real (era 13/11)
- [ ] Copiar os 6 limites da IN 75 com trechos literais, conferidos por outra pessoa (era 13/11)
- [ ] Indexar os textos no ChromaDB (`base_conhecimento_v1`) e testar 3 perguntas (era 13/11)
- [ ] Combinar com o Caio e o João as colunas de `metricas_requisicao` (monitoramento é R6/R7 e ADR-008)
- [ ] Regras de extração do OCR e checagens (22/11, semana 4)

**João (R1+R2)**
- [ ] ADRs (14/11): rascunho com 8 entregue em 13/11; faltam 005 com configs A/B/C e regra +5 pts / ≤ 3 s; 007 e 008 como aprovados (008 com PostgreSQL, sem Prometheus); 004 com coordenador por regras e ≤ 2 chamadas ao LLM; detalhes do 002
- [ ] 5 perguntas: versão de 13/11 cobre tudo; faltam C9 (PostgreSQL no lugar de Prometheus), "reindexação" na resposta 4 e escopo de alergênicos/itens fora
- [ ] Coordenador, agente de comparação e verificação por regras (14/11)

**Carlos (R5)**
- [ ] API FastAPI, agente nutricional e verificador com LLM ligável (14/11)

**Caio (R6+R7)**
- [ ] Estrutura do repositório, Docker Compose e CI com GitHub Actions (até 18/11)

**Gustavo (R3, líder)**
- [ ] Revisar o rascunho do conjunto de teste e conferir o gabarito nas fontes (era 13/11)
- [ ] Conferir os 6 limites da IN 75 que o Davi copiar
- [ ] Benchmark do verificador A/B/C (14/11, pode ir para 18/11)

**Decisões em aberto**
- [ ] Definir qual OCR fica (benchmark da semana 4)
- [ ] Escolher o modelo alternativo ao Gemini
- [ ] Aprovar ou não as checagens extras sugeridas pelo Davi (comentadas no SQL)
