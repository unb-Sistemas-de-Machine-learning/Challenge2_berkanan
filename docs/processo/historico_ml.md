# Histórico do processo de Machine Learning (Desafio 2, Equipe Berkanan)

> **Para que serve:** registrar, em ordem, o que fizemos de Machine Learning, por que fizemos, o que medimos e o que aprendemos. É a base da apresentação e do relatório final.
> **Foco:** dados, modelos, recuperação (RAG), construção do assistente e avaliação. Backend, frontend e banco aparecem só quando explicam uma decisão de ML.
> **Mantido por:** Gustavo (R3), com contribuições de toda a equipe. Última atualização: 21/11/2026.

## Como registrar uma nova entrada

Acrescente no fim da seção certa (ou na linha do tempo), sempre com:
- **Data** e **quem**;
- **O que** foi feito ou decidido;
- **Por quê** (o problema ou a hipótese);
- **Evidência** (número, teste, link do PR ou da issue);
- **Aprendizado** (o que mudou no nosso entendimento).

Resultados ainda não medidos ficam marcados como `PENDENTE`. Nunca registre resultado obtido com o backend em modo simulado como se fosse real.

---

## Linha do tempo resumida

| Data | Marco | Por que importa para ML |
|---|---|---|
| 05/11 | Tema escolhido: escolhas alimentares a partir do rótulo | Define a tarefa: ler o rótulo, explicar e comparar, com base em fontes oficiais |
| 11/11 | Feedback do professor muda a arquitetura | LLM deixa de ser o centro: OCR + regras primeiro, LLM só como reserva; números vêm do banco |
| 12/11 | Essential Question aprovada | Passa a guiar as métricas: "orientar de forma rápida e confiável" |
| 13/11 | Primeiro conjunto de teste (50 perguntas), escrito de memória | Avaliar antes de construir |
| 14/11 | Gabarito conferido nas fontes oficiais | Encontramos 15 respostas erradas ou desatualizadas no próprio gabarito |
| 16/11 | Dados estruturados carregados (TACO, limites da IN 75) e textos das fontes preparados para o RAG | Tratamento de dados: PDF → tabela, regras para valores ausentes |
| 17/11 | Revisão das fontes encontra a tabela da IN 75 embaralhada pela extração do PDF | Qualidade do dado afeta diretamente o que o LLM vai citar |
| 17/11 | Primeira medição do recall da busca: **13%** (meta 80%) | O RAG, como estava, quase não encontrava o trecho certo |
| 20/11 | Grade de experimentos: modelo de embeddings × tamanho do trecho | Melhor resultado: 33%; descobrimos o corte de texto pelos modelos |
| 21/11 | Cálculo do "ALTO EM" feito por código, testado com o gabarito | Separar o que o LLM explica do que o código calcula |
| 21/11 | Avaliação com usuários desenhada | Medir se a resposta **orienta**, não só se está correta |

---

## 1. O problema e como chegamos à pergunta

- **Problema:** as pessoas escolhem alimentos por rótulos difíceis de ler, marketing e redes sociais. A informação confiável existe (Guia Alimentar, ANVISA), mas está em documentos longos que ninguém consulta na hora da compra.
- **05/11:** o tema de atividade física foi descartado e ficamos com escolhas alimentares a partir do rótulo.
- **12/11, Essential Question:** "Como a IA pode usar os rótulos de produtos e fontes oficiais para ajudar a orientar os consumidores brasileiros a escolher opções mais saudáveis de forma rápida e confiável?"
- **Público:** consumidor adulto no supermercado, pelo celular. Grupo de maior risco: pessoas com diabetes ou hipertensão.
- **Escopo (12/11):** ler o rótulo, explicar nutrientes e %VD, avisar sobre alergênicos, comparar dois produtos, responder dúvidas com fonte e dizer "não há evidência suficiente" quando não souber. **Fora:** diagnóstico, dieta individual, marcas, transgênicos.

**Aprendizado:** cada parte da Essential Question virou uma métrica: "confiável" virou acerto, fidelidade e recusa correta; "rápida" virou tempo de resposta; "orientar" virou a avaliação com usuários.

---

## 2. A virada de 11/11: onde entra o LLM (e onde não entra)

**Antes:** a ideia inicial apoiava quase tudo no LLM (ler a foto, calcular e explicar).

**Depois do feedback do professor (11/11):**
| Tarefa | Quem faz | Por quê |
|---|---|---|
| Ler a foto do rótulo | OpenCV + OCR (Tesseract ou PaddleOCR) + regras | Mais barato, previsível e roda em CPU; LLM com visão só como reserva |
| Números (limites, "ALTO EM", comparação por 100 g) | Código + banco de dados | **O LLM não calcula nem inventa valores** |
| Explicar com citação | LLM + RAG (trechos das fontes oficiais) | É onde o LLM agrega: linguagem simples, sempre citando a fonte |
| Decidir o caminho (foto, pergunta, comparação) | Regras, sem LLM | No máximo 1 ou 2 chamadas ao LLM por resposta |
| Verificar a resposta | Regras ou LLM, **decidido por experimento** | Configurações A (sem), B (regras) e C (LLM): C só fica se ganhar ≥ 5 pontos de fidelidade com ≤ 3 s a mais |

**Aprendizado:** usar o LLM só onde ele é necessário reduz custo, latência e alucinação, e torna o sistema testável.

---

## 3. Avaliar antes de construir: o conjunto de teste

- **13/11:** 50 perguntas em 7 categorias: Guia Alimentar (10), rotulagem da ANVISA (10), cálculo do "ALTO EM" (8), comparação (6), alergênicos (5), saúde/OMS (5) e fora do escopo (6). O gabarito foi escrito **de memória**.
- **14/11, conferência nas fontes oficiais** (IN 75, RDC 429, RDC 727/2022, Lei 10.674, Guia Alimentar e OMS): 15 linhas corrigidas, entre elas:
  - **Queijo (C05):** o gabarito dizia "ALTO EM gordura saturada e sódio", mas a IN 75 (Anexo XVI) **proíbe** o selo em queijos, mesmo acima dos limites.
  - **Pão (A05):** o Guia classifica pão de forma e pães industrializados como **ultraprocessados**, não como processados.
  - **Alergênicos (E01, E04, E05):** citavam normas **revogadas** (RDC 26/2015 e RDC 136/2017, substituídas pela RDC 727/2022).
- **Ferramentas criadas:** validador do conjunto, executor dos benchmarks e cálculo das métricas (acerto, fidelidade, recusa correta, latência e chamadas ao LLM). PR #1.

**Aprendizado:** se até o gabarito feito por nós tinha erros, um LLM respondendo de memória teria os mesmos. Isso reforça a decisão de **sempre citar a fonte**. A "verdade" do teste tem que vir do documento oficial, não da memória de ninguém.

---

## 4. Dados: das fontes oficiais para algo que o sistema consegue usar

### 4.1 Dados estruturados (números)
- **TACO (16/11, Davi):** 597 alimentos por 100 g extraídos do PDF da 4ª edição por um extrator que usa a **posição do texto na página** (coordenadas), porque a tabela tem várias colunas. Regra de tratamento: `NA` (não analisado) e `Tr` (traços) viram **ausente**, nunca 0. Conferência por amostra: 3 alimentos iguais ao PDF em todas as colunas.
- **Limites do "ALTO EM" (16/11):** os 6 limites do Anexo XV da IN 75 (sólidos: 15 g, 6 g e 600 mg por 100 g; líquidos: 7,5 g, 3 g e 300 mg por 100 ml), guardados com o **trecho literal da norma** para citação. Conferidos contra o texto oficial.

### 4.2 Textos para o RAG
- **16/11:** textos do Guia, da IN 75, da RDC 429, da OMS e da SBD separados por página, com metadados para citar (documento, página, versão do índice). Divisão em trechos de 1000 caracteres com 150 de sobreposição.
- **17/11, problema encontrado:** na IN 75, a extração do PDF **misturou as duas colunas** da tabela do Anexo XV. A linha das gorduras saturadas ficou "3 g de Quantidade maior ou igual a 6 g de saturadas por 100 ml…". Um LLM lendo esse trecho poderia responder **6 g por 100 ml** para bebidas, e o certo é 3 g. Issue #27.
- **Correção proposta:** gerar as normas a partir do **texto HTML do Diário Oficial**, que preserva as tabelas, em vez do PDF.
- **17/11, decisão #20:** incluir a RDC 727/2022 e a Lei 10.674/2003 na base, porque sem elas as perguntas de alergênicos não têm fonte para citar.

**Aprendizado:** o modelo só é tão bom quanto o texto que recebe. Extração de PDF com tabela precisa ser conferida à mão. Valor ausente nunca é zero.

---

## 5. Recuperação (RAG): o experimento que mudou nosso plano

### 5.1 Como medir
- **17/11:** ferramenta de recall (PR #28). Para 30 perguntas que dependem de fonte, conta acerto quando um dos **3 primeiros trechos** é do documento certo **e contém, literalmente**, um trecho-chave do gabarito. Não depende do número da página.
- **Por que literal:** um teste anterior com resumo feito por outra IA mostrou um trecho que **não existia na página indicada** (juntava duas frases de lugares diferentes). Avaliação precisa usar a saída bruta da busca.
- **Teto da base atual:** 5 das 30 perguntas não podem ser acertadas (a tabela embaralhada e as normas de alergênicos ausentes), então o máximo possível hoje é 83%.

### 5.2 Primeira medição (17/11): 13%
O recall no top 3 foi de **13,3%** (meta: 80%). A causa: nem a ingestão nem a busca informavam um modelo de embeddings, então o ChromaDB usou o **padrão dele, em inglês** (`all-MiniLM-L6-v2`), para textos e perguntas em português. No Desafio 1 usávamos um modelo multilíngue; essa configuração se perdeu na migração.

### 5.3 Grade de experimentos (20/11)

| Modelo de embeddings | Trechos de 1000/150 | Trechos de 500/100 |
|---|---|---|
| `all-MiniLM-L6-v2` (inglês, padrão do ChromaDB) | 13,3% | 6,7% |
| `paraphrase-multilingual-MiniLM-L12-v2` (o do Desafio 1) | 13,3% | **33,3%** |
| `intfloat/multilingual-e5-base` | **33,3%** | **33,3%** |

O que os números mostraram:
1. **O modelo em inglês é o pior** e deve sair.
2. **Corte do texto:** o modelo do Desafio 1 só lê 128 tokens, e um trecho de 1000 caracteres tem uns 250. Com trechos de 500, ele passa a ler o trecho inteiro e vai de 13% para 33%. O `e5-base` lê até 512 tokens e vai bem nos dois tamanhos.
3. **Documento certo, trecho errado:** em várias perdas a busca acha a norma certa, mas não a tabela, que está embaralhada.
4. **Idioma:** as diretrizes da OMS estão em inglês e as perguntas em português; o `e5-base` não acertou nenhuma.

**Recomendação para a `base_conhecimento_v2`:** modelo configurado igual na ingestão e na busca, trechos de 500/100, textos limpos (normas pelo HTML oficial) e nova medição. `PENDENTE`.

**Aprendizado:** o tamanho do trecho tem que caber na janela do modelo de embeddings; trocar só o modelo não resolve; e um teste com 3 perguntas "parecia bom", mas não mostrava o problema. Sem a medição com o conjunto inteiro, teríamos seguido com 13%.

---

## 6. Construção do assistente

- **14/11, ponto de partida:** o backend recebido tinha respostas fixas (modo simulado), preservado como registro histórico. Nenhum resultado dele vale como evidência.
- **14/11, coordenador por regras (João):** decide o caminho (foto, pergunta ou comparação) **sem chamar o LLM**. Também o agente de comparação (descritivo) e o verificador por regras (configuração B), com testes.
- **16/11, contrato do benchmark:** a API passou a aceitar `verifier_mode` ("rules" ou "llm"), para medir B contra C.
- **21/11, cálculo do "ALTO EM" por código (PR #31):** normaliza a porção para 100 g ou 100 ml, recusa leitura inconsistente (açúcares maiores que carboidratos), compara com os limites e devolve o **trecho literal da norma** para o LLM citar. Valor não lido fica como "não avaliado". **20 testes tirados do gabarito.**
- **21/11, exceções do Anexo XVI (#21):** proposta de que o usuário informe o tipo de produto na tela de confirmação (o OCR não identifica com segurança que é um queijo) e que o sistema mostre os valores sem afirmar o selo. Aguardando decisão.

**Aprendizado:** separar o que é cálculo (código, testável, sem alucinação) do que é explicação (LLM com fonte). O gabarito do conjunto de teste virou teste automático do código.

---

## 7. Escolha de modelos de linguagem

- **LLM principal:** Gemini, que também é a reserva para ler a foto quando o OCR falha. Versão exata: `PENDENTE` (precisa ser fixada e registrada antes dos benchmarks).
- **21/11, modelo alternativo (#22, João):** o Ollama foi cogitado. Discussão: o Ollama roda o modelo, mas a escolha real é **qual modelo** (desempenho em português, obediência à fonte) e **em que máquina** (memória e tempo de resposta; meta ≤ 10 s). Para **imagem**, modelos de visão locais são pesados e erram mais em tabela nutricional. Proposta: separar as funções. A reserva de texto pode ser local ou uma API; sem Gemini, a reserva da foto vira **pedir correção ao usuário**, o que a arquitetura já prevê. Decisão: `PENDENTE`, com teste de 10 perguntas.
- **Embeddings:** ver seção 5.

---

## 8. Extração do rótulo (OCR)

- **14/11, como medir:** ferramenta de acerto **campo a campo** (meta ≥ 85%), separando o acerto da linha "ALÉRGICOS" e destacando o **falso negativo** (alergênico que estava no rótulo e não foi lido), que é o risco mais grave. Valor inventado conta como erro.
- **Protocolo de ~30 fotos:** 10 a 12 produtos em condições diferentes (boa, torta, reflexo, curva, pouca luz, borrada, cortada), com gabarito digitado e conferido por uma segunda pessoa.
- **Benchmark Tesseract × PaddleOCR × Gemini:** `PENDENTE` (semana 4).

---

## 9. Avaliação com usuários

- **21/11, desenho:** 5 tarefas tiradas do conjunto de teste (ler um rótulo, comparar, alergênicos, perfil de saúde simulado, fora do escopo), uma nota de 1 a 5 por tarefa ("clara e útil para decidir"), meta ≥ 4. Anônima, sem dados de saúde, coletada por Google Forms (PR #33).
- **Por quê:** as outras métricas dizem se a resposta está **certa**; só esta diz se ela **orienta** uma pessoa comum.
- **Aplicação:** 30/11 a 02/12 (#34). `PENDENTE`.

---

## 10. Aprendizados até aqui

1. **Medir antes de acreditar.** O recall de 13% só apareceu porque medimos com o conjunto inteiro; o teste com 3 perguntas não mostrava o problema.
2. **A qualidade do dado decide.** Uma tabela embaralhada na extração do PDF bastaria para o sistema citar um limite errado.
3. **O gabarito também erra.** Conferir nas fontes oficiais encontrou 15 problemas, incluindo normas revogadas.
4. **O LLM explica, o código calcula.** Números e regras normativas ficam em código testável; o LLM só redige com a fonte.
5. **Configuração de modelo é decisão de projeto, não detalhe.** O modelo de embeddings "sumiu" na migração do Desafio 1 e ninguém percebeu até medir.
6. **Tamanho do trecho e janela do modelo andam juntos.**
7. **Avaliar com a saída bruta.** O resumo de outra IA mostrou um trecho que não existia na página citada.

---

## 11. Resultados que ainda vão entrar

| Experimento | Métrica e meta | Situação |
|---|---|---|
| Recall com a `base_conhecimento_v2` | ≥ 80% no top 3 | `PENDENTE` (#27, #20 e embeddings) |
| LLM puro × RAG | RAG ≥ 15 pontos acima do LLM puro | `PENDENTE` (modelo Gemini a fixar) |
| Verificador A × B × C | C fica se ganhar ≥ 5 pts de fidelidade com ≤ 3 s a mais | `PENDENTE` (#12, #13) |
| Extração do rótulo | ≥ 85% dos campos; falsos negativos de alergênicos | `PENDENTE` (#8, #18) |
| Tempo de resposta | Mediana ≤ 10 s no 4G | `PENDENTE` (semana 5) |
| Avaliação com usuários | Nota média ≥ 4 de 5 | `PENDENTE` (#34) |
