# CLAUDE.md — Ponto de Entrada Rápido (Challenge 2 Berkanan)

Este arquivo orienta o Claude Code e demais assistentes de IA no repositório do **Challenge 2 Berkanan** (UnB — Sistemas de Machine Learning, 2026/02).

## 1. Documentos Canônicos (Leia Primeiro)

Para evitar duplicação e divergência de contexto, toda a governança e documentação normativa estão centralizadas nos seguintes arquivos:

- **Regras obrigatórias para agentes:** [AGENTS.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/AGENTS.md)
- **Índice completo do projeto e estado em 14/11/2026:** [docs/context/INDEX.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/INDEX.md)
- **Manifesto de documentos e ADRs (SHA-256):** [docs/context/MANIFEST.yaml](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/MANIFEST.yaml)
- **Fontes originais preservadas:**
  - [docs/context/sources/contextoCLAUDEV2.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/sources/contextoCLAUDEV2.md)
  - [docs/context/sources/adr.pdf](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/sources/adr.pdf)
  - [docs/context/sources/5_perguntas_escopo_essential_question.pdf](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/context/sources/5_perguntas_escopo_essential_question.pdf)
- **Baseline do Backend (`backend-whatsapp-v0.1.0`):** [docs/baselines/backend-whatsapp-v0.1.0.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/baselines/backend-whatsapp-v0.1.0.md)
- **Matriz de responsabilidades (R1–R7):** [docs/handoff/RESPONSIBILITIES.md](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/docs/handoff/RESPONSIBILITIES.md)

## 2. Comandos Úteis de Verificação e Execução

```bash
# 1. Verificar integridade SHA-256 do snapshot original e das fontes documentais
python3 scripts/verify_baseline.py

# 2. Validar sintaxe Python do backend
python3 -m py_compile backend/*.py

# 3. Executar a API FastAPI localmente (dentro de backend/)
cd backend && uvicorn main:api --host 0.0.0.0 --port 8000

# 4. Executar smoke tests automatizados (com asserções de contrato HTTP/JSON)
bash scripts/smoke_backend.sh

# 5. Validar e subir infraestrutura Docker Compose
docker compose config
docker compose up --build -d
```

## 3. Lembretes Críticos

1. **Código executável do backend:** reside exclusivamente em [backend/](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/backend) (`uvicorn main:api`).
2. **Snapshots imutáveis:** [snapshots/backend/whatsapp-v0.1.0/original/](file:///home/caio/Documentos/GitHub/Challenge2_berkanan/snapshots/backend/whatsapp-v0.1.0/original) é arquivo de preservação histórica — **não edite**.
3. **Estado atual do backend:** esqueleto funcional com respostas simuladas em `backend/graph.py`. Não declare integrações com PostgreSQL, ChromaDB ou OCR como implementadas até que o código real seja entregue por R2/R4/R5.
4. **Restrições arquiteturais:** Sem cálculos pelo LLM, citação obrigatória do RAG, máximo de 1–2 chamadas ao LLM por resposta, confirmação obrigatória do OCR pelo usuário, monitoramento via PostgreSQL (**sem Prometheus**).
