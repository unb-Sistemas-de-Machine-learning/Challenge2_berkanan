# Gabaritos das fotos de rótulos (um arquivo por pessoa)

Cada integrante coloca aqui o gabarito das próprias fotos, num arquivo com o nome da sua faixa de produtos (issue #18):

| Arquivo | Responsável | Quem confere |
|---|---|---|
| `P01-P03.csv` | Gustavo | João |
| `P04-P06.csv` | João | Davi |
| `P07-P09.csv` | Davi | Carlos |
| `P10-P12.csv` | Carlos | Caio |
| `P13-P15.csv` | Caio | Gustavo |

**Como preencher:**
1. Copie o cabeçalho de [../gabarito_fotos_modelo.csv](../gabarito_fotos_modelo.csv).
2. Uma linha por foto. O `foto_id` é o nome do arquivo da foto sem extensão (ex.: `P04_boa`, `P04_reflexo`), e o número do produto precisa estar na sua faixa.
3. Siga as regras de digitação do [protocolo](../protocolo_fotos.md), seção 4: valor exatamente como impresso na coluna por 100 g ou 100 ml, campo que não existe no rótulo fica vazio, alergênicos só com o nome do alimento separados por `;`.
4. Antes de abrir o PR, valide a pasta inteira:

```bash
cd mlops/experiments
python -m benchmark.extraction --validar testset/gabarito_fotos/
```

O validador aponta foto fora da sua faixa, `foto_id` repetido entre arquivos, coluna faltando, `tipo` diferente de `solido`/`liquido` e açúcares totais maiores que carboidratos.

As **fotos não vão para o Git**: ficam na pasta compartilhada do Google Drive (link no grupo da equipe).
