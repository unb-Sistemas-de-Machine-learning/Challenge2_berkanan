-- ============================================================================
-- MIGRAÇÃO 010: segunda conferência das fontes oficiais (issue #2)
-- DATA: 21/11/2026 · Conferente: Gustavo Oki (R3), a pedido do R4 (Davi)
-- DEPENDE DA 009 (nome e link das fontes da OMS).
--
-- Marca como 'conferido' só as fontes cujo documento foi aberto e cujo conteúdo
-- foi comparado com o texto oficial. A SBD continua pendente: o link abre, mas o
-- conteúdo ainda não foi conferido.
--
-- O que foi conferido (detalhes em mlops/experiments/testset/conferencia_gabarito.md
-- e nos comentários das issues #2, #6 e #26):
--   Guia Alimentar  PDF do Ministério da Saúde; trechos do gabarito (cats. A e D)
--                   conferidos com página. Corrige também a falta de link num banco novo.
--   RDC 429/2020    texto do DOU de 09/10/2020; arts. 2º, 5º, 8º, 12, 18, 19, 50 e 51.
--   IN 75/2020      texto do DOU de 09/10/2020; Anexos II, XV e XVI.
--   TACO            PDF da 4ª edição (164 páginas); 3 alimentos conferidos com a
--                   migração 007 em todas as colunas carregadas.
--   OMS (açúcares e sódio)  PDFs no IRIS da OMS; título e recomendações conferidos.
--
-- Não edita migrações anteriores. Idempotente: pode rodar mais de uma vez.
-- ============================================================================

-- 1. Guia Alimentar: num banco novo, nenhuma migração preenchia link e data do download.
UPDATE fontes_documentos
SET
    link = COALESCE(link, 'https://bvsms.saude.gov.br/bvs/publicacoes/guia_alimentar_populacao_brasileira_2ed.pdf'),
    data_download = COALESCE(data_download, DATE '2026-11-14'),
    link_verificado_em = COALESCE(link_verificado_em, DATE '2026-11-17'),
    link_verificado_por = COALESCE(link_verificado_por, 'Gustavo Oki (R3)')
WHERE documento = 'Guia Alimentar para a População Brasileira';

-- 2. Marca como conferido (o CHECK chk_fontes_conferido_completo exige versão, link,
--    data do download e conferente preenchidos; se faltar algo, a migração falha).
UPDATE fontes_documentos
SET
    status_conferencia = 'conferido',
    conferido_por = 'Gustavo Oki (R3) - segunda conferência',
    observacoes = CASE
        WHEN observacoes LIKE '%Conferido em 2%' THEN observacoes
        ELSE COALESCE(NULLIF(observacoes, '') || ' ', '') || CASE documento
            WHEN 'Guia Alimentar para a População Brasileira' THEN
                'Conferido em 21/11/2026: PDF oficial do Ministério da Saúde; trechos do gabarito conferidos com página.'
            WHEN 'RDC 429/2020' THEN
                'Conferido em 21/11/2026: texto do DOU de 09/10/2020 (arts. 2º, 5º, 8º, 12, 18, 19, 50 e 51).'
            WHEN 'IN 75/2020' THEN
                'Conferido em 21/11/2026: texto do DOU de 09/10/2020 (Anexos II, XV e XVI); limites da migração 008 iguais ao Anexo XV.'
            WHEN 'Tabela Brasileira de Composição de Alimentos (TACO)' THEN
                'Conferido em 21/11/2026: PDF da 4ª edição; amostra de 3 alimentos igual à migração 007 em todas as colunas carregadas.'
            ELSE
                'Conferido em 21/11/2026: PDF da diretriz no IRIS da OMS; título e recomendações conferidos.'
        END
    END
WHERE documento IN (
    'Guia Alimentar para a População Brasileira',
    'RDC 429/2020',
    'IN 75/2020',
    'Tabela Brasileira de Composição de Alimentos (TACO)',
    'OMS – Guideline: Sugars intake for adults and children',
    'OMS – Guideline: Sodium intake for adults and children'
);

-- 3. SBD: continua pendente, com o motivo registrado.
UPDATE fontes_documentos
SET observacoes = COALESCE(NULLIF(observacoes, '') || ' ', '')
    || 'Pendente em 21/11/2026: link abre, mas o conteúdo ainda não foi conferido.'
WHERE documento = 'Diretrizes da Sociedade Brasileira de Diabetes (SBD)'
  AND status_conferencia = 'pendente_conferencia'
  AND (observacoes IS NULL OR observacoes NOT LIKE '%Pendente em 21/11/2026%');
