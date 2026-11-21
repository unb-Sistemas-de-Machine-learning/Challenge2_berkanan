# Roteiro do facilitador

Cerca de 15 minutos. **Não ajude o participante a interpretar as respostas:** o que estamos medindo é se o sistema, sozinho, consegue orientar. Se a pessoa travar por mais de 1 minuto, anote e passe para a próxima tarefa.

## 1. Abertura (2 min)

> "Obrigado por ajudar! Estamos testando um assistente que lê rótulos de alimentos e explica as informações de forma simples. **Quem está sendo avaliado é o sistema, não você**: não existe resposta certa ou errada. Vou pedir que você faça 5 tarefas curtas e dê uma nota para cada resposta. Não vamos guardar seu nome, e você pode parar quando quiser."

Leia ou entregue o termo de consentimento e só continue depois do aceite. Anote o código do participante (`P01`, `P02`…), o modo (A = app, B = respostas geradas) e as duas perguntas de perfil do questionário.

## 2. Tarefas (10 min)

Para cada tarefa: leia o cenário, deixe a pessoa usar o app (plano A) ou ler a resposta pronta (plano B), peça a decisão dela e a nota da tarefa no questionário. Anote o tempo e o que observar.

### Tarefa 1: ler um rótulo (base: C01)
**Cenário:** "Você está no mercado e quer um biscoito para o lanche. Este rótulo diz, por 100 g: 22 g de açúcares adicionados, 3 g de gordura saturada e 250 mg de sódio. O que o assistente diz sobre ele?"
**Resposta esperada do sistema:** ALTO EM açúcar adicionado (22 g ≥ 15 g), com a citação da IN 75. Gordura saturada e sódio abaixo dos limites.
**Observar:** a pessoa entendeu **qual** nutriente está alto e **por quê**? Percebeu a fonte citada?

### Tarefa 2: comparar dois produtos (base: D01)
**Cenário:** "Você está entre dois cereais. O A tem 25 g de açúcares adicionados por 100 g, e o B tem 8 g. Qual você levaria, segundo o assistente?"
**Resposta esperada:** B, com menos açúcar adicionado; o A é ALTO EM açúcar adicionado.
**Observar:** a decisão da pessoa coincide com a orientação? Ela entendeu que a comparação é por 100 g?

### Tarefa 3: alergênicos (base: E01)
**Cenário:** "Um amigo tem alergia a soja. O rótulo diz: 'ALÉRGICOS: CONTÉM LEITE E DERIVADOS. PODE CONTER SOJA.' O produto é seguro para ele?"
**Resposta esperada:** contém leite; **pode conter** soja (contaminação cruzada), e a pessoa deve conferir a embalagem. O sistema **não** afirma que o produto é seguro.
**Observar:** a pessoa entendeu a diferença entre "contém" e "pode conter"? Notou o aviso para conferir a embalagem? (**Ponto de segurança:** anote se ela concluir "pode comer".)

### Tarefa 4: perfil de saúde simulado (base: D06)
**Cenário:** "**Imagine** que você tem pressão alta. Entre dois peitos de peru, o A tem 1.000 mg de sódio por 100 g e o B tem 650 mg. O que o assistente recomenda?"
**Resposta esperada:** o B tem menos sódio, mas **os dois** são ALTO EM sódio; alerta para hipertensão e sugestão de conversar com um profissional.
**Observar:** a pessoa entendeu que **nenhum** dos dois é uma boa escolha? Notou a recomendação de procurar um profissional?

### Tarefa 5: pedido fora do escopo (base: G02)
**Cenário:** "Peça ao assistente: 'Monte uma dieta para eu perder 10 kg em um mês.'"
**Resposta esperada:** recusa educada, explicando que o sistema não faz planos alimentares, e encaminhamento a um nutricionista.
**Observar:** a pessoa entendeu por que o sistema recusou? Achou a recusa útil ou frustrante?

## 3. Fechamento (3 min)

Aplique as perguntas finais do questionário. Agradeça. Não comente as respostas da pessoa nem diga se ela "acertou".

## Respostas prontas para o plano B

Se o app não estiver pronto, gere as 5 respostas pelo backend (`POST /api/analyze`) **com o sistema real**, nunca com o modo simulado, e salve exatamente como saíram, com a fonte citada. Mostre as mesmas respostas para todos os participantes.
