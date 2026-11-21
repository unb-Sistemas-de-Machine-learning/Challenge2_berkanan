-- ============================================================================
-- MIGRAÇÃO 009: fontes da OMS (issue #26)
-- DATA: 20/11/2026 · Responsável: Gustavo (R3), a pedido da revisão das fontes
--
-- Corrige o cadastro das duas diretrizes da OMS em fontes_documentos:
--   1. A 001 criou 'Diretrizes sobre açúcares e sódio' (açúcares e sódio juntos),
--      mas a 006 procura 'OMS – Guideline: Sugars intake for adults and children'
--      e cria o sódio separado. Num banco novo, o UPDATE da seção 4 da 006 não
--      altera nada. Aqui a fonte passa a se chamar só açúcares, e o sódio continua
--      no registro próprio criado pela 006.
--   2. Os links apontavam para a página de apresentação da OMS. Passam a apontar
--      para o PDF da diretriz no repositório IRIS da OMS (download direto).
--
-- Não edita a 006 (migração já aplicada). Idempotente: pode rodar mais de uma vez.
-- Links abertos e conferidos (título e nº de páginas do PDF) em 20/11/2026.
-- ============================================================================

-- 1. Renomeia a fonte de açúcares (só se o nome antigo existir e o novo ainda não).
UPDATE fontes_documentos
SET documento = 'OMS – Guideline: Sugars intake for adults and children'
WHERE documento = 'Diretrizes sobre açúcares e sódio'
  AND NOT EXISTS (
      SELECT 1 FROM fontes_documentos
      WHERE documento = 'OMS – Guideline: Sugars intake for adults and children'
  );

-- 2. Açúcares: PDF da diretriz (Guideline: Sugars intake for adults and children, OMS, 2015; 59 páginas).
UPDATE fontes_documentos
SET
    versao = 'Guideline: Sugars intake for adults and children (OMS, 2015)',
    link = 'https://iris.who.int/server/api/core/bitstreams/4be74f01-de93-4596-bbd1-02a97afb1221/content',
    data_download = COALESCE(data_download, DATE '2026-11-20'),
    link_verificado_em = DATE '2026-11-20',
    link_verificado_por = 'Gustavo Oki (R3)',
    observacoes = CASE
        WHEN observacoes LIKE '%Página de apresentação:%' THEN observacoes
        ELSE COALESCE(NULLIF(observacoes, '') || ' ', '')
             || 'Página de apresentação: https://www.who.int/publications/i/item/9789241549028'
    END
WHERE documento = 'OMS – Guideline: Sugars intake for adults and children';

-- 3. Sódio: PDF da diretriz (Guideline: Sodium intake for adults and children, OMS, 2012).
UPDATE fontes_documentos
SET
    versao = COALESCE(versao, 'Guideline: Sodium intake for adults and children (OMS, 2012)'),
    link = 'https://iris.who.int/server/api/core/bitstreams/d0f9feb5-ed78-44d1-9e06-533a93352012/content',
    link_verificado_em = DATE '2026-11-20',
    link_verificado_por = 'Gustavo Oki (R3)',
    observacoes = CASE
        WHEN observacoes LIKE '%Página de apresentação:%' THEN observacoes
        ELSE COALESCE(NULLIF(observacoes, '') || ' ', '')
             || 'Página de apresentação: https://www.who.int/publications-detail/9789241504836'
    END
WHERE documento = 'OMS – Guideline: Sodium intake for adults and children';
