# Histórico do processo de Machine Learning (Desafio 2, Equipe Berkanan)

> **Para que serve:** registrar, em ordem, o que fizemos de Machine Learning, por que fizemos, o que medimos e o que aprendemos. É a base da apresentação e do relatório final.
> **Foco:** dados, modelos, recuperação (RAG), construção do assistente e avaliação. Backend, frontend e banco aparecem só quando explicam uma decisão de ML.
> **Mantido por:** Gustavo (R3), com contribuições de toda a equipe. Última atualização: 24/11/2026.

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
| 22/11 | Recall da v2: 100% com regras feitas para o teste, **53%** sem elas | Contaminação pelo conjunto de teste, detectada e corrigida |
| 22/11 | Conjunto de validação (25 perguntas novas): recall de **28%** | A busca generaliza mal para perguntas com outras palavras |

---

## 0. Ponto de partida: a crítica ao Desafio 1

**O que fizemos no Desafio 1:** um classificador de notícias (FAKE ou REAL) treinado com **TF-IDF + MultinomialNB** em **164 exemplos** (130 de treino e 34 de teste). O modelo foi escolhido por GridSearchCV entre 4 algoritmos e várias combinações, pelo F1 da classe FAKE, e chegou a **F1 de 0,978** no teste.

**A crítica do professor:** com tão poucos dados, o modelo provavelmente estava em **overfitting**.

**Por que ele tinha razão:**
- O TF-IDF transforma cada palavra (e par de palavras) do vocabulário numa variável. Com 130 exemplos e milhares de variáveis, o modelo **decora as palavras** daqueles textos em vez de aprender o padrão. O próprio README já dizia que ele "aprende estilo de escrita, não medicina".
- Escolher entre muitas configurações **nos mesmos poucos dados** favorece a que se ajustou por acaso.
- Com 34 exemplos de teste, **cada erro muda o resultado em cerca de 3 pontos**: o 0,978 parecia muito mais preciso do que era.

O problema não era o F1 (que só mede) nem o TF-IDF (que só representa o texto), e sim **treinar e escolher o modelo com poucos dados e avaliá-lo num conjunto pequeno**.

**O que mudou no Desafio 2 por causa disso:**
1. **Não treinamos nenhum modelo.** Usamos modelos já treinados (embeddings multilíngues e Gemini) e regras e cálculos determinísticos. O conjunto de teste serve **só para avaliar**, nunca para ajustar.
2. **Quando o mesmo risco apareceu de outra forma** (regras da busca escritas para as perguntas do teste, seção 5.4), ele foi detectado pela própria medição e corrigido.
3. **O conjunto de teste também é pequeno, então os resultados são estimativas.** Cada pergunta vale 3,3 pontos no recall (30 perguntas) e 2 pontos nas métricas de 50 perguntas. A regra do verificador ("C só fica com ≥ 5 pontos de fidelidade") corresponde a 2 ou 3 respostas, por isso as 3 repetições e a leitura com margem.
4. **Ajustes vão para um conjunto de validação separado**, com perguntas novas, e o conjunto de teste fica só para a medição final. Criado em 22/11 (seção 5.5).

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

### 5.4 `base_conhecimento_v2` e a contaminação pelo conjunto de teste (21 e 22/11)
- **21/11, v2 (Davi, PR #38):** normas geradas a partir do HTML oficial (corrige a tabela da IN 75), RDC 727/2022 e Lei 10.674/2003 incluídas, cabeçalhos dos PDFs limpos, modelo multilíngue configurado igual na ingestão e na busca, trechos de 500/100 (1.947 trechos) e uma busca **híbrida**, que soma a similaridade por significado com a sobreposição de palavras e bigramas da pergunta.
- **22/11, primeira medição: 100%.** Bom demais para ser verdade, considerando 13% na v1 e 33% no melhor teste da grade. Conferindo o código, a busca tinha **31 regras escritas para as próprias perguntas do teste**: cada regra era disparada por palavras da pergunta e empurrava para o topo o trecho com **as mesmas frases-chave do gabarito de recall**. Isso é **contaminação pelo conjunto de teste**: o sistema foi ajustado com as respostas da prova.
- **Medição sem as regras: 53,3%** (A 60%, B 70%, D 100%, E 25%, F 20%). É o resultado oficial da v2: um ganho real de 13% para 53%, ainda abaixo da meta de 80%. Os pontos fracos são os alergênicos (E) e a OMS em inglês (F).
- **Correção (22/11, PR #41):** as regras foram removidas; a busca híbrida genérica foi mantida.

**Aprendizado:** resultado perfeito pede auditoria, não comemoração. Um conjunto de teste só mede alguma coisa enquanto não é usado para ajustar o sistema. Para ajustar a busca sem contaminar a medição, é preciso um **conjunto de validação separado**, com perguntas novas escritas com outras palavras.

### 5.5 Conjunto de validação: o 53% era otimista (22/11)
- **O que fizemos (PR #42):** 25 perguntas novas (Guia 7, rotulagem 7, alergênicos 5, OMS e SBD 6), escritas com palavras diferentes das do teste (no máximo 50% de palavras em comum). Os trechos-chave do gabarito foram escolhidos lendo as fontes, sem olhar o que a busca recupera, e trechos genéricos demais (que aparecem em muitas páginas) foram trocados por específicos.
- **Regra de uso:** ajustes da busca são testados na **validação**, e só com mudanças genéricas; o **teste** fica congelado para a medição final.

| Busca da v2 | Conjunto de teste (30) | **Validação (25)** |
|---|---|---|
| Sem as regras do teste (oficial) | 53,3% | **28,0%** (A 57%, B 14%, E 40%, F 0%) |
| Com as regras do teste | 100% | 40,0% |

- **A busca generaliza mal:** com perguntas novas, o recall cai de 53% para 28%, e a rotulagem (B) despenca para 14%. Como a v2 foi construída olhando para o conjunto de teste, é natural que funcione melhor nele.
- **As regras eram quase só memorização:** davam +47 pontos no teste e só +12 na validação. Os 12 pontos vêm de 3 perguntas em que a regra funcionava como **ponte genérica por tema** (sódio e açúcar levando à OMS em inglês, glúten levando à lei), um caminho legítimo para testar na validação, sem copiar frases do gabarito.
- **Ressalva:** com 25 perguntas, o intervalo de confiança do 28% vai de cerca de 14% a 48%; parte da diferença pode vir da dificuldade das perguntas.
- **A escolha do modelo reserva (#22) também usa a validação** (`benchmark/comparar_llm.py`, PR #44), pelo mesmo motivo.

**Aprendizado:** um resultado só vale para o conjunto em que foi medido. Medir em perguntas novas mostrou que a distância até a meta de 80% é maior do que o teste indicava.

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
8. **Não ajustar o sistema com o conjunto de teste.** Regras escritas para as perguntas da prova levaram o recall a 100%; sem elas, o valor real era 53%. Ajustes precisam de um conjunto de validação separado.
9. **Com poucos dados, todo número é uma estimativa.** Foi a crítica ao Desafio 1 (F1 de 0,978 em 34 exemplos) e vale aqui: com 30 a 50 perguntas, uma diferença de poucos pontos pode ser só variação.

---

## 11. Resultados que ainda vão entrar

| Experimento | Métrica e meta | Situação |
|---|---|---|
| Recall com a `base_conhecimento_v2` | ≥ 80% no top 3 | **53,3%** no teste e **28,0%** na validação em 22/11, abaixo da meta (seções 5.4 e 5.5) |
| LLM puro × RAG | RAG ≥ 15 pontos acima do LLM puro | `PENDENTE` (modelo Gemini a fixar) |
| Verificador A × B × C | C fica se ganhar ≥ 5 pts de fidelidade com ≤ 3 s a mais | `PENDENTE` (#12, #13) |
| Extração do rótulo | ≥ 85% dos campos; falsos negativos de alergênicos | `PENDENTE` (#8, #18) |
| Tempo de resposta | Mediana ≤ 10 s no 4G | `PENDENTE` (semana 5) |
| Avaliação com usuários | Nota média ≥ 4 de 5 | `PENDENTE` (#34) |
