# Conferência do gabarito nas fontes oficiais (14/11/2026)

> **Responsável:** Gustavo (R3). Conferência do rascunho de 13/11 (`conjunto_de_teste.csv`, 50 perguntas).
> **Status:** `CONFERIDO` com 15 linhas corrigidas e 3 pontos para o grupo decidir (seção 3).

## 1. Fontes usadas

| Fonte | Onde foi lida | Observação |
|---|---|---|
| IN 75/2020 (ANVISA) | DOU, publicação de 09/10/2020 (in.gov.br) | Anexos II (VDR), XV (limites ALTO EM) e XVI (lupa vedada) |
| RDC 429/2020 (ANVISA) | DOU, publicação de 09/10/2020 (in.gov.br) | Arts. 2º, 5º, 8º, 12, 18, 19, 50 e 51. Texto original; alterações posteriores não foram conferidas |
| RDC 727/2022 (ANVISA) | DOU, publicação de 06/07/2022 (in.gov.br) | Arts. 13, 14, 18 e 40 (revogações). Em vigor desde 01/09/2022 |
| Lei 10.674/2003 | planalto.gov.br | Art. 1º |
| Guia Alimentar para a População Brasileira, 2ª ed. | PDF do Ministério da Saúde (bvsms.saude.gov.br) | Páginas citadas pela numeração impressa |
| OMS | Fichas "Healthy diet" e "Sodium reduction" (who.int) | Açúcares livres e sódio |

## 2. Resultado por linha

**Sem alteração (confirmadas na fonte):** A01 (Guia, p. 25), A02 (p. 50), A04 (p. 33 e 49), A07 (p. 26), A08 (p. 29), A10 (p. 125), B02 e B03 (RDC 429, arts. 8º e 18), B04 a B07 (IN 75, Anexo XV), C01 a C04, C06 a C08, D01 a D03, D05, D06, E03, F01 a F04, G01 a G06.

**Corrigidas:**

| ID | O que mudou | Base |
|---|---|---|
| **C05** | **Erro de gabarito.** Queijo sem ingredientes opcionais que agreguem gordura saturada ou sódio **não pode** ter a lupa, mesmo passando dos limites. O gabarito dizia "ALTO EM gordura saturada e sódio" | IN 75, Anexo XVI, item 6: "Queijos, desde que não sejam adicionados de ingredientes opcionais que agreguem [...]"; RDC 429, art. 18, § 1º: "é vedada a veiculação da informação" |
| **A05** | O gabarito tratava todo pão como processado. Pães de forma, de hambúrguer e pães doces industrializados são **ultraprocessados** | Guia, p. 36–37 (processados: "pães feitos de farinha de trigo, leveduras, água e sal") e p. 41 (ultraprocessados: "pães de forma, pães para hambúrguer ou hot dog, pães doces") |
| A03 | Definição trocada pelo texto do Guia | Guia, p. 41: "formulações industriais feitas inteiramente ou majoritariamente de substâncias extraídas de alimentos [...]" |
| A06 | Incluído "frequentemente cinco ou mais" ingredientes | Guia, p. 40 |
| A09 | Identificado como o passo 10 | Guia, p. 128 |
| B01 | Acrescentado que nutrientes com alegação também entram | RDC 429, art. 5º, I a XIII |
| B08 | Definições alinhadas à norma: lactose adicionada conta como açúcar adicionado; açúcar de suco integral não conta | RDC 429, art. 2º, I e II |
| B09 | Datas e prazos exatos | RDC 429, arts. 50 e 51; publicação em 09/10/2020 |
| B10, F05 | Base de 2.000 kcal citada pela fonte | RDC 429, art. 12; IN 75, Anexo II |
| D04 | Classificação exata dos dois iogurtes | Guia, p. 29 ("iogurte (sem adição de açúcar)") e p. 41 ("iogurtes e bebidas lácteas adoçados e aromatizados") |
| **E01, E05** | **Fonte revogada.** A RDC 26/2015 foi revogada pela RDC 727/2022 | RDC 727/2022, art. 40, V; frases obrigatórias nos arts. 13 e 14 |
| **E04** | **Fonte revogada.** A RDC 136/2017 foi revogada; "CONTÉM LACTOSE" é obrigatório acima de 100 mg/100 g ou ml | RDC 727/2022, art. 40, VI e art. 18 |
| E02 | Fonte completada | Lei 10.674/2003, art. 1º ("contém Glúten" / "não contém Glúten"); RDC 727/2022 |

As 7 linhas marcadas com `Conferir na fonte = Sim` (A03, A06, A09, B07, B09, E02, F05) foram conferidas e agora estão como `Não`.

**Não conferida:** F03 cita a SBD, mas o documento da SBD do Desafio 1 não foi identificado. O gabarito (alertar, não prescrever, encaminhar) segue as regras do projeto, então a linha continua válida para medir segurança.

## 3. Pontos para o grupo decidir

1. **Fontes de alergênicos fora da base (afeta R4 e R1/R2).** As perguntas E01, E02, E04 e E05 citam a RDC 727/2022 e a Lei 10.674/2003, que **não estão** entre as 5 fontes da base de conhecimento. Sem elas, o RAG não tem o que citar, e essas linhas vão falhar em fidelidade e recall. Opções: incluir as duas no ChromaDB e em `fontes_documentos` (recomendado, porque alergênicos estão no escopo aprovado) ou reescrever as perguntas para depender só da regra do projeto.
2. **Exceções do Anexo XVI da IN 75 (afeta R4, R2 e R5).** O cálculo do "ALTO EM" não pode só comparar com os 6 limites. Queijos, leites, leites fermentados, ovos, carnes in natura, frutas, farinhas, óleos vegetais, sal e outros não podem ter a lupa (Anexo XVI), salvo para o nutriente alterado por ingrediente adicionado (RDC 429, art. 18, § 2º). Isso precisa estar no banco (ex.: uma tabela de exceções numa nova migração) e no agente. A C05 passa a testar exatamente esse caso.
3. **Alterações posteriores da RDC 429.** Conferi o texto original de 2020. Se houve resolução posterior mudando prazos ou regras, B09 pode precisar de ajuste. Vale o Davi conferir ao registrar a fonte.
