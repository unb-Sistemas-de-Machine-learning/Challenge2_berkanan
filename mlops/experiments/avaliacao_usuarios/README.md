# Avaliação com usuários (métrica 10, semana 6)

> **Responsável:** Gustavo (R3). **Status:** `PROPOSTO` em 21/11/2026 (materiais prontos; aplicação na semana 6).
> **Meta aprovada (seção 9):** nota média de clareza e utilidade **≥ 4 de 5**, com 5 a 10 pessoas.

## Por que fazer

A Essential Question pergunta se a IA ajuda a **orientar** o consumidor a escolher melhor, de forma **rápida e confiável**. Acerto, fidelidade e recusa correta medem o "confiável", e o tempo de resposta mede o "rápida". Só a avaliação com pessoas mede se a resposta **orienta de fato**, ou seja, se alguém sem formação em nutrição entende a resposta e consegue decidir com ela.

## Formato

| Item | Decisão |
|---|---|
| Participantes | 5 a 10 adultos que fazem compras no supermercado. Sem exigir formação na área |
| Duração | Cerca de 15 minutos por pessoa, presencial ou por chamada de vídeo |
| Tarefas | 5, tiradas do conjunto de teste ([roteiro.md](roteiro.md)) |
| Nota oficial | Uma nota de 1 a 5 por tarefa ("quanto a resposta foi clara e útil para decidir"), que corresponde a `metricas_requisicao.avaliacao_usuario_nota` |
| Coleta | **Google Forms** ligado a uma **planilha Google**, criados pelo script [criar_formulario.gs](criar_formulario.gs) |
| Quando | Começo da semana 6 (30/11 a 02/12), para caber no relatório de 07/12 |

**Plano A (app):** a pessoa usa o app no próprio celular ou num celular de teste.
**Plano B (se o app não estiver pronto):** a pessoa avalia **respostas já geradas** pelo sistema para as mesmas tarefas, em tela ou impressas. A nota medida é a mesma, mas o modo fica registrado na planilha e no relatório.

## Cuidados (LGPD e ética)

- **Anônima:** cada pessoa vira `P01`, `P02`… Nome e contato não vão para a planilha nem para o repositório.
- **Sem dados de saúde:** não perguntamos se a pessoa tem diabetes ou hipertensão. A tarefa 4 usa um perfil **simulado**.
- **Fotos:** só de embalagens, nunca da pessoa nem da tela com dados dela.
- **Consentimento** antes de começar ([termo_consentimento.md](termo_consentimento.md)). A pessoa pode parar a qualquer momento.
- **Confirmar com o professor** se uma avaliação de usabilidade anônima de disciplina precisa de alguma aprovação formal.

## Arquivos

| Arquivo | Para quê |
|---|---|
| [criar_formulario.gs](criar_formulario.gs) | Script do Google (Apps Script) que cria o formulário e a planilha de uma vez |
| [roteiro.md](roteiro.md) | O que o facilitador fala e faz, as 5 tarefas e o que observar |
| [questionario.md](questionario.md) | As mesmas perguntas do formulário, para conferência ou para aplicar em papel |
| [termo_consentimento.md](termo_consentimento.md) | Texto do termo, que também é a primeira página do formulário |

## Como criar o formulário (uma vez só)

1. Acesse https://script.google.com com a conta Google da equipe e crie um **Novo projeto**.
2. Cole o conteúdo de [criar_formulario.gs](criar_formulario.gs) e **preencha a constante `RESPONSAVEL`** no topo (nome e contato de quem responde às dúvidas). O script se recusa a rodar sem ela.
3. Salve e execute a função `criarAvaliacao`, autorizando o acesso pedido.
4. Em **Registro de execução** aparecem três links: o formulário para os participantes, o formulário para edição e a planilha de respostas.
5. Abra o formulário e confira: o termo é a primeira página, e quem não concorda é levado direto ao envio, sem responder nada.
6. Compartilhe a planilha só com os integrantes da equipe.

O formulário não coleta e-mail nem exige login. O participante é identificado só pelo código que o facilitador informa (P01, P02…).

## Como consolidar

1. **Respostas dos participantes:** caem sozinhas na aba de respostas da planilha.
2. **Observações do facilitador** (tempo, se a decisão coincidiu com a orientação, se notou o aviso ou a fonte): preenchidas na aba *Observações do facilitador*, uma linha por participante e tarefa.
3. **Resultado:** a aba *Resumo* calcula sozinha a nota média por tarefa e a geral, o percentual de notas 4 ou 5 e se a meta (média ≥ 4) foi atingida.
4. **No relatório:** número de participantes, modo (A ou B), médias por tarefa, tarefas concluídas e os principais comentários.
5. Se o app estiver integrado à telemetria, as notas também podem ir para `metricas_requisicao.avaliacao_usuario_nota`, e a visão `vw_avaliacao_usuarios` confere a meta no banco.
