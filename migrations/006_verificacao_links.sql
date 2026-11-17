-- ============================================================================
-- ARQUIVO: migrations/006_verificacao_links.sql
-- DESCRIÇÃO: Registra a verificação empírica de abertura dos links no navegador
--            realizada pelo Davi em 16/11/2026.
--            Adiciona colunas link_verificado_em e link_verificado_por.
--            Atualiza as linhas cujos links conferem exatamente com a checagem.
--            Adiciona nota sobre download do PDF do DOU para RDC 429 e IN 75.
--            Adiciona constraint de integridade para verificação de links.
--            NÃO altera conferido_por nem status_conferencia.
-- AUTOR: Davi Rodrigues (R4 Engenheiro de Dados) - Equipe Berkanan
-- DATA: 16/11/2026
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. NOVAS COLUNAS PARA TELEMETRIA DE VERIFICAÇÃO DE LINKS (IDEMPOTENTE)
-- ----------------------------------------------------------------------------
ALTER TABLE fontes_documentos
    ADD COLUMN IF NOT EXISTS link_verificado_em DATE,
    ADD COLUMN IF NOT EXISTS link_verificado_por VARCHAR(100);

COMMENT ON COLUMN fontes_documentos.link_verificado_em IS 'Data em que o link foi testado e aberto com sucesso no navegador.';
COMMENT ON COLUMN fontes_documentos.link_verificado_por IS 'Responsável que abriu e confirmou o funcionamento do link.';

-- ----------------------------------------------------------------------------
-- 2. CONSTRAINT DE INTEGRIDADE IDEMPOTENTE
-- Garante que uma linha só pode ter link_verificado_em se link não for nulo.
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_fontes_link_verificado'
    ) THEN
        ALTER TABLE fontes_documentos
            ADD CONSTRAINT chk_fontes_link_verificado
            CHECK (link_verificado_em IS NULL OR link IS NOT NULL);
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 3. REGISTRO DE VERIFICAÇÃO DOS LINKS (ABRIU E FUNCIONA - 16/11/2026)
-- Se o link do banco for diferente do listado, a linha NÃO é marcada.
-- ----------------------------------------------------------------------------

-- 1. Tabela Brasileira de Composição de Alimentos (TACO)
UPDATE fontes_documentos
SET
    link_verificado_em = '2026-11-16',
    link_verificado_por = 'Davi Rodrigues (R4)'
WHERE documento = 'Tabela Brasileira de Composição de Alimentos (TACO)'
  AND link = 'https://cfn.org.br/wp-content/uploads/2017/03/taco_4_edicao_ampliada_e_revisada.pdf';

-- 2. Diretrizes da Sociedade Brasileira de Diabetes (SBD)
UPDATE fontes_documentos
SET
    link_verificado_em = '2026-11-16',
    link_verificado_por = 'Davi Rodrigues (R4)'
WHERE documento = 'Diretrizes da Sociedade Brasileira de Diabetes (SBD)'
  AND link = 'https://diretriz.diabetes.org.br/terapia-nutricional-no-pre-diabetes-e-no-diabetes-mellitus-tipo-2/';

-- 3. Guia Alimentar para a População Brasileira
UPDATE fontes_documentos
SET
    link_verificado_em = '2026-11-16',
    link_verificado_por = 'Davi Rodrigues (R4)'
WHERE documento = 'Guia Alimentar para a População Brasileira'
  AND link = 'https://bvsms.saude.gov.br/bvs/publicacoes/guia_alimentar_populacao_brasileira_2ed.pdf';

-- 4. OMS – Guideline: Sugars intake for adults and children
UPDATE fontes_documentos
SET
    link_verificado_em = '2026-11-16',
    link_verificado_por = 'Davi Rodrigues (R4)'
WHERE documento = 'OMS – Guideline: Sugars intake for adults and children'
  AND link = 'https://www.who.int/publications/i/item/9789241549028';

-- 5. RDC 429/2020
UPDATE fontes_documentos
SET
    link_verificado_em = '2026-11-16',
    link_verificado_por = 'Davi Rodrigues (R4)'
WHERE documento = 'RDC 429/2020'
  AND link = 'https://www.in.gov.br/en/web/dou/-/resolucao-de-diretoria-colegiada-rdc-n-429-de-8-de-outubro-de-2020-282070599';

-- 6. IN 75/2020
UPDATE fontes_documentos
SET
    link_verificado_em = '2026-11-16',
    link_verificado_por = 'Davi Rodrigues (R4)'
WHERE documento = 'IN 75/2020'
  AND link = 'https://www.in.gov.br/en/web/dou/-/instrucao-normativa-in-n-75-de-8-de-outubro-de-2020-282071143';

-- ----------------------------------------------------------------------------
-- 4. REGISTRO DE PDF SALVO DO DOU (RDC 429/2020 e IN 75/2020)
-- Concatena a nota apenas se ainda não contiver 'PDF salvo'.
-- ----------------------------------------------------------------------------
UPDATE fontes_documentos
SET observacoes = COALESCE(observacoes, '') || ' PDF salvo pelo Davi em 16/11/2026 (texto original do DOU; não substitui a versão certificada).'
WHERE documento = 'RDC 429/2020'
  AND (observacoes IS NULL OR observacoes NOT LIKE '%PDF salvo%');

UPDATE fontes_documentos
SET observacoes = COALESCE(observacoes, '') || ' PDF salvo pelo Davi em 16/11/2026 (texto original do DOU; não substitui a versão certificada).'
WHERE documento = 'IN 75/2020'
  AND (observacoes IS NULL OR observacoes NOT LIKE '%PDF salvo%');

-- ----------------------------------------------------------------------------
-- 5. REGISTRO DA LINHA 'OMS – Guideline: Sodium intake for adults and children'
-- Linha informada pelo Davi em 16/11/2026.
-- Link da página cadastrado, data de download registrada e nota de PDF adicionada.
-- link_verificado_em/por permanece NULL porque o Davi abriu o link do PDF (IRIS),
-- não confirmando ainda a abertura no navegador da página HTML do link da WHO.
-- ----------------------------------------------------------------------------
INSERT INTO fontes_documentos (
    documento,
    orgao,
    versao,
    link,
    data_download,
    status_conferencia,
    observacoes
) VALUES (
    'OMS – Guideline: Sodium intake for adults and children',
    'OMS',
    NULL,
    'https://www.who.int/publications-detail/9789241504836',
    '2026-11-16',
    'pendente_conferencia',
    'PDF informado pelo Davi (download direto, aberto em 16/11/2026): https://iris.who.int/server/api/core/bitstreams/d0f9feb5-ed78-44d1-9e06-533a93352012/content'
)
ON CONFLICT (documento) DO UPDATE
SET
    link = EXCLUDED.link,
    data_download = EXCLUDED.data_download,
    observacoes = CASE
        WHEN fontes_documentos.observacoes IS NULL OR fontes_documentos.observacoes = '' THEN EXCLUDED.observacoes
        WHEN fontes_documentos.observacoes NOT LIKE '%PDF informado pelo Davi%' THEN fontes_documentos.observacoes || ' ' || EXCLUDED.observacoes
        ELSE fontes_documentos.observacoes
    END;

