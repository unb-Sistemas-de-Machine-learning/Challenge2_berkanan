# Orientação global para agentes e colaboradores

Este documento é compartilhado e versionável. Aplica-se ao contexto do projeto e a todos os papéis R1–R7; não atribui uma persona pessoal ao assistente. O ponto de entrada de governança do repositório é o [AGENTS.md da raiz](../../AGENTS.md).

## Contexto e fontes

O Challenge 2 Berkanan é uma PoC acadêmica de apoio à leitura de rótulos nutricionais, comparação de produtos e perguntas com evidências oficiais, por uma interface web Mobile First. Não realiza diagnóstico nem prescrição.

Leia nesta ordem:

1. [INDEX.md](INDEX.md): visão geral, escopo, arquitetura e estado registrado.
2. [MANIFEST.yaml](MANIFEST.yaml): origem, integridade e status das fontes e ADRs.
3. Fontes em `sources/`: texto original das decisões e requisitos.
4. [RESPONSIBILITIES.md](../handoff/RESPONSIBILITIES.md): responsáveis e interfaces de entrega.
5. Código e configurações relacionados à tarefa: evidência do estado atual.

Os originais preservados definem os status documentais; resumos não aprovam decisões. Código demonstra implementação, mas não aprovação arquitetural. Ao encontrar divergências, registre-as e consulte o responsável antes de mudar uma decisão.

## Arquitetura e estado de referência

- FastAPI centraliza a API; LangGraph organiza os fluxos com coordenador por regras.
- PostgreSQL destina-se aos dados estruturados e métricas; ChromaDB aos textos recuperados pelo RAG.
- OCR é executado no servidor, com confirmação dos valores pelo usuário. O motor depende de benchmark.
- O backend canônico está em `backend/`, com `main:api` e `POST /api/analyze`. O snapshot histórico está em `snapshots/backend/whatsapp-v0.1.0/`.
- Na referência de 14/11/2026, o grafo retorna dados simulados, sem integração real com OCR, bancos ou LLM. Existem Dockerfile, Compose, CI e estrutura inicial MLOps; sua presença não comprova execução bem-sucedida nem integração funcional.

Confira os arquivos atuais antes de reutilizar essa referência. Diferencie estado aprovado, proposto, pendente, simulado e verificado, registrando evidências e data ou commit da inspeção.

## Coordenação do trabalho

Use a matriz de responsabilidades para identificar quem implementa e revisa cada componente. A tarefa solicitada define o papel de atuação; não limite todos os colaboradores a R6/R7.

Antes de implementar, identifique o comportamento esperado, arquivos afetados, dependências de outras entregas e critério de aceite. Mudanças em contratos da API, estado do grafo, migrações ou configuração exigem atualização dos consumidores e coordenação com os responsáveis.

Preserve snapshots e fontes originais. Não sobrescreva trabalho existente nem migrações aplicadas. Não apresente benchmarks, aprovações ou resultados de testes sem evidências.

Valide de acordo com a mudança: integridade com `python3 scripts/verify_baseline.py`; API em execução com `bash scripts/smoke_backend.sh`; infraestrutura com `bash infra/scripts/check_compose.sh` e build quando aplicável. Informe resultados, limitações e dependências restantes. Commits dependem de solicitação do usuário.

## Contexto particular de cada colaborador

Anotações pessoais, personas e planos individuais podem ficar em `.local/`, diretório ignorado pelo Git. Esse conteúdo é opcional, não constitui documentação canônica e não deve ser necessário para executar ou compreender o projeto.

Para usar uma persona particular, indique explicitamente o caminho do documento local na sessão. Arquivos em `.local/` não são carregados automaticamente por este guia. Mantenha links particulares dentro desse material; documentos compartilhados devem depender apenas de arquivos versionados.
