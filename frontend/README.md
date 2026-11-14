# Frontend — Aplicação Web Mobile First (Pendente)

> **Status atual (14/11/2026):** `PENDENTE` — Aguardando entrega da implementação por **R5 (Carlos — Engenheiro de Software)**.

## 1. Escopo e Tecnologias Aprovadas

- **Stack aprovada:** React + Vite + Tailwind CSS.
- **Formato de entrega:** Aplicação web responsiva (**Mobile First**) executada diretamente no navegador do celular.
- **Proibições de escopo:** Não implementar aplicativo nativo Android/iOS, PWA ou OCR local no dispositivo sem aprovação prévia.

## 2. Fluxo Esperado no Dispositivo Móvel (ADR-002 e ADR-003)

1. Capturar a fotografia da tabela nutricional e da seção `"ALÉRGICOS"` do rótulo.
2. Permitir recorte básico e realizar **compressão da imagem no navegador antes do envio**:
   - Dimensão máxima de referência: **~1280 pixels** no maior lado;
   - Formato: **JPEG**;
   - Tamanho máximo aproximado: **até 300 KB** (preservando a legibilidade dos números e unidades).
3. Enviar a imagem comprimida / consulta para a API FastAPI (`POST /api/analyze` e futuras rotas de extração).
4. **Exibir os campos extraídos pelo OCR para revisão e confirmação obrigatória do usuário** antes da análise nutricional ou comparação.
5. Apresentar a análise fundamentada com citações das fontes oficiais, alertas para diabetes/hipertensão (quando aplicável), aviso obrigatório sobre alergênicos (conferir a embalagem) e aviso fixo de que o sistema não substitui orientação médica ou nutricional.

## 3. Integração com Infraestrutura (R6)

Assim que o código inicial (`package.json`, `vite.config.ts`, `src/`) for adicionado a este diretório por R5, o serviço `frontend` e a respectiva etapa de validação na CI (`.github/workflows/ci.yml`) serão ativados por R6.
