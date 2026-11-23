# Protocolo das fotos de rótulos (benchmark de extração, semana 4)

> **Responsável:** Gustavo (R3). **Status:** `PROPOSTO` em 14/11/2026.
> Mede o acerto da extração (meta ≥ 85% dos campos) e o tempo por foto de cada motor (Tesseract, PaddleOCR, Gemini), conforme o ADR-002.

## 1. Quais fotos tirar

Cerca de **10 a 12 produtos**, cada um fotografado em **2 ou 3 condições**, num total de **~30 fotos**. Assim o gabarito é digitado uma vez por produto, e dá para comparar a mesma tabela em condições diferentes.

| Condição (`condicao`) | Qtd. | Como tirar |
|---|---|---|
| `boa` | 10 | Tabela reta, bem iluminada, preenchendo a maior parte da foto |
| `torta` | 4 | Celular inclinado, cerca de 20° a 30° |
| `reflexo` | 4 | Embalagem brilhante com reflexo de luz sobre parte da tabela |
| `curva` | 4 | Garrafa, lata ou pacote em que a tabela fica curvada |
| `pouca_luz` | 3 | Ambiente escuro, sem flash |
| `borrada` | 2 | Leve tremida ou fora de foco (ainda legível para uma pessoa) |
| `cortada` | 3 | Linha "ALÉRGICOS" fora do quadro ou parte da tabela cortada |

**Critérios para escolher os produtos:**
- Só rótulos no **padrão novo** (RDC 429/2020): coluna por 100 g ou 100 ml e linha de açúcares adicionados.
- **Pelo menos 4 líquidos** (bebidas, leites, sucos) e o restante sólidos.
- **Pelo menos 6 com a linha "ALÉRGICOS"**, sendo ao menos 2 com "PODE CONTER".
- **Pelo menos 3 com a lupa "ALTO EM"** e 2 sem ela.
- Variar o tamanho da embalagem: incluir ao menos 2 com tabela pequena (letra miúda).

## 2. Como nomear e guardar

- Nome do arquivo: `P<produto>_<condicao>.jpg`. Exemplos: `P01_boa.jpg`, `P01_reflexo.jpg`, `P07_curva.jpg`. O nome sem extensão é o `foto_id`.
- Guardar o **original** e uma **versão comprimida igual à do app** (~1280 px no maior lado, JPEG, até ~300 KB). O benchmark oficial usa a comprimida, porque é ela que chega ao servidor.
- **As fotos não vão para o Git** (`testset/fotos/` está no `.gitignore`). Ficam na pasta compartilhada da equipe no Google Drive (subpastas "originais" e "comprimidas"; link no grupo); no repositório entram só o gabarito e os resultados.
- **O grupo todo fotografa** (issue #18): cada pessoa tem uma faixa de produtos (P01–P03, P04–P06…), para ninguém repetir nome de arquivo.

## 3. Cuidados (LGPD)

- Fotografar **só a embalagem**: sem rostos, pessoas, documentos, notas fiscais ou telas.
- **Remover a localização (GPS)** das fotos antes de compartilhar, ou desligar a localização da câmera.
- No relatório, preferir recortes só da tabela, sem destacar marcas, porque o sistema não recomenda marcas.

## 4. Como digitar o gabarito

Cada pessoa cria o **seu arquivo** em [gabarito_fotos/](gabarito_fotos/), com o nome da sua faixa (ex.: `P04-P06.csv`), copiando o cabeçalho de [gabarito_fotos_modelo.csv](gabarito_fotos_modelo.csv). Uma linha por foto. Fotos do mesmo produto repetem os valores e mudam só `foto_id` e `condicao`.

| Coluna | Como preencher |
|---|---|
| `foto_id` | Nome do arquivo sem extensão (`P01_boa`) |
| `tipo` | `solido` ou `liquido` |
| `condicao` | Uma das condições da seção 1 |
| `alergicos_visivel` | `sim` se a linha "ALÉRGICOS" aparece legível **nesta foto**; senão `não` |
| `valor_energetico_kcal` … `sodio_mg` | Valor **exatamente como impresso na coluna por 100 g ou 100 ml**. Vírgula ou ponto como decimal, sem separador de milhar (`1000`, não `1.000`). Vazio se o rótulo não tem o campo |
| `porcao_g` | Tamanho da porção em g ou ml, como impresso |
| `alergicos_contem` | Alimentos após "CONTÉM", separados por `;`, só o nome do alimento (`leite; trigo`). "CONTÉM LEITE E DERIVADOS" vira `leite` |
| `alergicos_pode_conter` | Mesmo formato, para "PODE CONTER" |

Valores como "0" e "zero" viram `0`. Se a tabela diz "não contém quantidade significativa", também é `0`.

**Dupla conferência:** quem digita não confere. Outra pessoa compara cada linha com a foto original antes de o gabarito valer. Erros de digitação viram erros falsos do OCR.

O validador recusa `foto_id` repetido, `tipo` inválido e açúcares totais maiores que carboidratos.

## 5. Formato que o pipeline de OCR deve entregar (contrato com R4 e R5)

Uma linha por **motor × foto** em `leituras.csv` ([leituras_modelo.csv](leituras_modelo.csv)), com as mesmas colunas numéricas e de alergênicos do gabarito, mais:

| Coluna | Conteúdo |
|---|---|
| `motor` | `tesseract`, `paddleocr`, `gemini` (ou o nome do motor testado) |
| `tempo_ms` | Tempo da foto recebida até os campos extraídos (pré-processamento + OCR + regras) |

Os valores devem ser os **lidos do rótulo**, antes da confirmação do usuário. Campo não encontrado fica vazio, nunca `0`.

## 6. Como rodar

```bash
cd mlops/experiments
python -m benchmark.extraction --validar testset/gabarito_fotos/        # confere todos os gabaritos
python -m benchmark.extraction testset/gabarito_fotos/ results/<experimento>/leituras.csv
```

O resultado mostra, por motor:
- acerto geral, por campo e por condição, e se atingiu a meta de 85%;
- recall dos alergênicos e a lista de fotos com **falso negativo** (alergênico do rótulo que não foi lido), que é o risco alto do projeto;
- tempo mediano por foto;
- cada erro, com o valor esperado e o lido.

**Custo:** Tesseract e PaddleOCR rodam em CPU local (custo zero por chamada). Para o Gemini, o custo por foto sai do número de chamadas e do preço da tabela do provedor na data do teste, registrado no relatório.

Comparação numérica: só conta acerto o valor igual ao impresso. Vazio no gabarito e na leitura não conta; vazio no gabarito com valor na leitura é erro (valor inventado).
