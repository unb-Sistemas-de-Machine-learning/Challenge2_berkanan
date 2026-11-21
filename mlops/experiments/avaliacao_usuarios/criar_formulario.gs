/**
 * Cria o formulário da avaliação com usuários (Google Forms) já ligado a uma planilha (Google Sheets).
 *
 * Como usar (uma vez só):
 *   1. Acesse https://script.google.com com a conta Google da equipe e clique em "Novo projeto".
 *   2. Apague o conteúdo, cole este arquivo inteiro e salve.
 *   3. Selecione a função `criarAvaliacao` e clique em "Executar". Autorize o acesso pedido.
 *   4. Veja em "Registro de execução" os links do formulário e da planilha.
 *
 * A planilha recebe as respostas e ganha duas abas:
 *   - "Observações do facilitador": tempo, decisão e o que foi observado em cada tarefa;
 *   - "Resumo": média por tarefa, média geral e a meta (>= 4 de 5). Rode `atualizarResumo`
 *     de novo se mudar os títulos das perguntas.
 *
 * Privacidade (LGPD): não coleta e-mail nem nome; o participante é identificado só pelo código (P01...).
 * Nenhuma pergunta sobre saúde. Equipe Berkanan, Gustavo (R3), métrica 10 da seção 9.
 */

// PREENCHA ANTES DE EXECUTAR: quem responde às dúvidas dos participantes (nome e forma de contato).
const RESPONSAVEL = 'PREENCHA: nome e contato do responsável pela avaliação';

const TITULO = 'Avaliação do assistente de rótulos nutricionais (Equipe Berkanan, UnB)';
const NOTA_AJUDA = '1 = nada clara nem útil · 3 = mais ou menos · 5 = muito clara e útil';

const TAREFAS = [
  ['T1', 'Ler um rótulo',
   'Você está no mercado e quer um biscoito para o lanche. O rótulo diz, por 100 g: 22 g de açúcares adicionados, 3 g de gordura saturada e 250 mg de sódio. Veja o que o assistente diz sobre ele.'],
  ['T2', 'Comparar dois produtos',
   'Você está entre dois cereais. O A tem 25 g de açúcares adicionados por 100 g, e o B tem 8 g. Veja qual o assistente indica.'],
  ['T3', 'Alergênicos',
   'Um amigo tem alergia a soja. O rótulo diz: "ALÉRGICOS: CONTÉM LEITE E DERIVADOS. PODE CONTER SOJA." Veja o que o assistente diz.'],
  ['T4', 'Perfil de saúde simulado',
   'IMAGINE que você tem pressão alta. Entre dois peitos de peru, o A tem 1.000 mg de sódio por 100 g e o B tem 650 mg. Veja o que o assistente recomenda.'],
  ['T5', 'Pedido fora do escopo',
   'Peça ao assistente: "Monte uma dieta para eu perder 10 kg em um mês." Veja como ele responde.'],
];

const TERMO = [
  'Você está sendo convidado(a) a avaliar um protótipo feito por estudantes da UnB na disciplina "Tópicos Especiais em Engenharia de Software: Sistemas de Machine Learning" (2026/2).',
  '',
  'O ASSISTENTE lê o rótulo nutricional de alimentos e explica as informações com base em fontes oficiais (Guia Alimentar do Ministério da Saúde e normas da ANVISA). Ele NÃO substitui a orientação de um médico ou nutricionista.',
  '',
  'VOCÊ VAI fazer 5 tarefas curtas e dar uma nota de 1 a 5 para cada resposta (cerca de 15 minutos).',
  '',
  'REGISTRAMOS suas notas, comentários, faixa de idade e se você costuma ler rótulos. NÃO registramos seu nome, contato, fotos suas nem informações sobre sua saúde. Quando uma tarefa fala de uma condição de saúde, ela é imaginária.',
  '',
  'Os dados ficam neste formulário e numa planilha Google da equipe, com acesso só dos integrantes, e serão usados apenas de forma agregada e anônima no relatório e na apresentação da disciplina. Você é identificado(a) só por um código (P01, P02...).',
  '',
  'A participação é voluntária: você pode desistir a qualquer momento e pedir que suas respostas sejam descartadas. Não há pagamento, custo nem risco previsto além do tempo dedicado.',
  '',
  'DÚVIDAS: ' + RESPONSAVEL + ' (estudante da equipe Berkanan).',
].join('\n');

function criarAvaliacao() {
  if (RESPONSAVEL.startsWith('PREENCHA')) {
    throw new Error('Preencha a constante RESPONSAVEL (nome e contato) no topo do script antes de executar.');
  }
  const form = FormApp.create(TITULO);
  form.setDescription('Avaliação anônima, cerca de 15 minutos. Quem está sendo avaliado é o assistente, não você: não existe resposta certa ou errada.');
  try { form.setEmailCollectionType(FormApp.EmailCollectionType.DO_NOT_COLLECT); } catch (e) { form.setCollectEmail(false); }
  form.setLimitOneResponsePerUser(false); // não exige login do participante
  form.setAllowResponseEdits(false);
  form.setShowLinkToRespondAgain(true);   // o facilitador pode reabrir no mesmo aparelho
  form.setProgressBar(true);
  form.setConfirmationMessage('Obrigado pela participação! Suas respostas foram registradas de forma anônima.');

  // 1. Consentimento: quem não concorda vai direto para o envio, sem responder nada.
  const consentimento = form.addMultipleChoiceItem()
    .setTitle('Termo de consentimento')
    .setHelpText(TERMO)
    .setRequired(true);

  // 2. Identificação (sem dados pessoais) e perfil.
  const paginaPerfil = form.addPageBreakItem().setTitle('Identificação e perfil');
  consentimento.setChoices([
    consentimento.createChoice('Li e entendi as informações e concordo em participar', paginaPerfil),
    consentimento.createChoice('Não concordo em participar', FormApp.PageNavigationType.SUBMIT),
  ]);

  form.addTextItem()
    .setTitle('Código do participante')
    .setHelpText('Informado pelo facilitador (ex.: P01).')
    .setRequired(true)
    .setValidation(FormApp.createTextValidation()
      .requireTextMatchesPattern('^P[0-9]{2}$')
      .setHelpText('Use o formato P01, P02...').build());
  form.addMultipleChoiceItem()
    .setTitle('Modo da sessão')
    .setHelpText('Preenchido pelo facilitador.')
    .setChoiceValues(['A (app)', 'B (respostas prontas)'])
    .setRequired(true);
  form.addMultipleChoiceItem()
    .setTitle('Faixa de idade')
    .setChoiceValues(['18–29', '30–44', '45–59', '60 ou mais'])
    .setRequired(true);
  form.addMultipleChoiceItem()
    .setTitle('Com que frequência você lê o rótulo nutricional antes de comprar?')
    .setChoiceValues(['Nunca', 'Às vezes', 'Quase sempre'])
    .setRequired(true);

  // 3. Uma página por tarefa: cenário, nota oficial (1 a 5) e comentário opcional.
  TAREFAS.forEach(([codigo, nome, cenario]) => {
    form.addPageBreakItem().setTitle(`Tarefa ${codigo.slice(1)}: ${nome}`).setHelpText(cenario);
    form.addScaleItem()
      .setTitle(`Nota ${codigo}: quanto esta resposta foi clara e útil para você decidir?`)
      .setHelpText(NOTA_AJUDA)
      .setBounds(1, 5).setLabels('Nada clara nem útil', 'Muito clara e útil')
      .setRequired(true);
    form.addParagraphTextItem().setTitle(`Comentário ${codigo} (opcional)`);
  });

  // 4. Perguntas finais.
  form.addPageBreakItem().setTitle('Para terminar');
  form.addScaleItem()
    .setTitle('Quanto você confiaria nas informações do assistente na hora da compra?')
    .setBounds(1, 5).setLabels('Nada', 'Totalmente').setRequired(true);
  form.addMultipleChoiceItem()
    .setTitle('Você percebeu o aviso de que o assistente não substitui a orientação de um médico ou nutricionista?')
    .setChoiceValues(['Sim', 'Não']).setRequired(true);
  form.addMultipleChoiceItem()
    .setTitle('Você usaria um assistente assim no supermercado?')
    .setChoiceValues(['Sim', 'Talvez', 'Não']).setRequired(true);
  form.addParagraphTextItem().setTitle('O que foi mais útil?');
  form.addParagraphTextItem().setTitle('O que foi confuso ou você mudaria?');

  // 5. Planilha de respostas, com as abas do facilitador e de resumo.
  const ss = SpreadsheetApp.create('Avaliação com usuários: respostas (Equipe Berkanan)');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
  SpreadsheetApp.flush();

  const obs = ss.insertSheet('Observações do facilitador');
  obs.appendRow(['participante_id', 'tarefa', 'decisao_coincide (sim/parcial/não)', 'tempo_s', 'notou_aviso_ou_fonte (sim/não)', 'observacao']);
  obs.setFrozenRows(1);
  obs.getRange('A1:F1').setFontWeight('bold');

  ss.insertSheet('Resumo');
  PropertiesService.getScriptProperties().setProperty('PLANILHA_ID', ss.getId());
  atualizarResumo();

  // O Google cria uma aba vazia "Página1"/"Sheet1" junto com a planilha; remove se ainda existir.
  ss.getSheets().filter(s => !s.getFormUrl() && /^(Página1|Sheet1)$/.test(s.getName()))
    .forEach(s => ss.deleteSheet(s));

  Logger.log('Formulário (enviar aos participantes): ' + form.getPublishedUrl());
  Logger.log('Formulário (edição): ' + form.getEditUrl());
  Logger.log('Planilha de respostas: ' + ss.getUrl());
}

/** Reescreve a aba "Resumo" com fórmulas que leem a aba de respostas pelo título de cada pergunta. */
function atualizarResumo() {
  const ss = SpreadsheetApp.openById(PropertiesService.getScriptProperties().getProperty('PLANILHA_ID'));
  const respostas = ss.getSheets().find(s => s.getFormUrl());
  if (!respostas) throw new Error('Aba de respostas do formulário não encontrada.');
  const cabecalho = respostas.getRange(1, 1, 1, respostas.getLastColumn()).getValues()[0];
  const coluna = prefixo => {
    const i = cabecalho.findIndex(t => String(t).startsWith(prefixo));
    if (i < 0) throw new Error('Pergunta não encontrada na planilha: ' + prefixo);
    const letra = respostas.getRange(1, i + 1).getA1Notation().replace(/[0-9]/g, '');
    return `'${respostas.getName()}'!${letra}2:${letra}`;
  };

  const resumo = ss.getSheetByName('Resumo');
  resumo.clear();
  const linhas = [['Tarefa', 'Respostas', 'Nota média (1 a 5)', '% com nota 4 ou 5', 'Meta (média ≥ 4)']];
  const intervalos = [];
  TAREFAS.forEach(([codigo, nome]) => {
    const r = coluna(`Nota ${codigo}`);
    intervalos.push(r);
    linhas.push([`${codigo} – ${nome}`, `=COUNT(${r})`, `=IFERROR(ROUND(AVERAGE(${r}),2),"Sem dados")`,
      `=IFERROR(COUNTIF(${r},">=4")/COUNT(${r}),"Sem dados")`,
      `=IFERROR(IF(AVERAGE(${r})>=4,"Atingida","Abaixo"),"Sem dados")`]);
  });
  const todos = intervalos.join(',');
  linhas.push(['GERAL (todas as tarefas)', `=COUNT(${todos})`, `=IFERROR(ROUND(AVERAGE(${todos}),2),"Sem dados")`,
    `=IFERROR(SUM(${intervalos.map(r => `COUNTIF(${r},">=4")`).join(',')})/COUNT(${todos}),"Sem dados")`,
    `=IFERROR(IF(AVERAGE(${todos})>=4,"Atingida","Abaixo"),"Sem dados")`]);
  const confianca = coluna('Quanto você confiaria');
  linhas.push(['Confiança (pergunta final)', `=COUNT(${confianca})`, `=IFERROR(ROUND(AVERAGE(${confianca}),2),"Sem dados")`, '', '']);

  const destino = resumo.getRange(1, 1, linhas.length, 5);
  destino.setFormulas(linhas); // Apps Script grava fórmulas sempre em inglês (vírgula), qualquer que seja o idioma
  resumo.getRange('A1:E1').setFontWeight('bold');
  resumo.getRange(2, 4, linhas.length - 1, 1).setNumberFormat('0%');
  resumo.setFrozenRows(1);
  resumo.autoResizeColumns(1, 5);
}
