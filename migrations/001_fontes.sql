-- ============================================================================
-- ARQUIVO: migrations/001_fontes.sql
-- DESCRIÇÃO: Cria a tabela fontes_documentos com as 5 fontes oficiais listadas
--            no CLAUDE.md (Seção 6), em 6 registros: RDC 429/2020 e IN 75/2020
--            são uma fonte só no CLAUDE.md, mas ficam em registros separados
--            porque os limites da rotulagem frontal vêm do texto da IN 75.
--            Campos não verificados ficam NULL.
-- REVISÃO 14/11: tabelas que apontam para cá devem buscar o id pelo nome do
--            documento, nunca por número fixo (o SERIAL depende da ordem).
-- AUTOR: Davi Rodrigues (R4 Engenheiro de Dados) - Equipe Berkanan
-- DATA: 13/11/2026
-- ============================================================================

CREATE TABLE IF NOT EXISTS fontes_documentos (
    id                      SERIAL PRIMARY KEY,
    documento               VARCHAR(150) NOT NULL UNIQUE,
    orgao                   VARCHAR(120) NOT NULL,
    versao                  VARCHAR(100), -- aceita NULL (a confirmar ao baixar)
    link                    TEXT,         -- aceita NULL (a confirmar ao baixar)
    data_download           DATE,         -- aceita NULL, sem valor padrão (a confirmar ao baixar)
    conferido_por           VARCHAR(100), -- aceita NULL, sem valor padrão (a confirmar ao baixar)
    
    -- SUGESTÃO do Davi, não aprovada pelo grupo (não consta no material):
    hash_arquivo            VARCHAR(64),
    
    status_conferencia      VARCHAR(30) NOT NULL DEFAULT 'pendente_conferencia'
                            CHECK (status_conferencia IN ('pendente_conferencia', 'conferido', 'obsoleto')),
    observacoes             TEXT,
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE fontes_documentos IS 'Repositório de governança das fontes oficiais citadas no CLAUDE.md.';
COMMENT ON COLUMN fontes_documentos.hash_arquivo IS 'SUGESTÃO do Davi, não aprovada pelo grupo (não consta no material).';
COMMENT ON COLUMN fontes_documentos.data_download IS 'Data do download (NULL até a efetiva realização do download).';
COMMENT ON COLUMN fontes_documentos.conferido_por IS 'Conferente da fonte (NULL até a efetiva conferência).';

CREATE INDEX IF NOT EXISTS idx_fontes_documentos_doc ON fontes_documentos (documento);

-- ----------------------------------------------------------------------------
-- CARGA DAS 5 FONTES OFICIAIS DO CLAUDE.MD (SEÇÃO 6), EM 6 REGISTROS:
-- 1. Guia Alimentar para a População Brasileira (2ª ed., 2014) - Ministério da Saúde
-- 2. RDC 429/2020 - ANVISA
-- 3. IN 75/2020 - ANVISA
-- 4. Tabela Brasileira de Composição de Alimentos (TACO) - NEPA/Unicamp
-- 5. Diretrizes sobre açúcares e sódio - OMS
-- 6. Diretrizes da Sociedade Brasileira de Diabetes (SBD) - SBD (documentos já usados no Desafio 1)
--
-- PENDÊNCIA (CLAUDE.MD): A lista foi montada de memória; versões e links
-- precisam ser conferidos ao baixar. Portanto, versao e link iniciam como NULL
-- (exceto a versão da 2ª ed., 2014 do Guia que consta expressamente no material).
-- ----------------------------------------------------------------------------
INSERT INTO fontes_documentos (
    documento,
    orgao,
    versao,
    link,
    data_download,
    conferido_por,
    status_conferencia,
    observacoes
) VALUES
(
    'Guia Alimentar para a População Brasileira',
    'Ministério da Saúde',
    '2ª ed., 2014',
    NULL,
    NULL,
    NULL,
    'pendente_conferencia',
    'versão e link a confirmar ao baixar'
),
(
    'RDC 429/2020',
    'ANVISA',
    NULL,
    NULL,
    NULL,
    NULL,
    'pendente_conferencia',
    'versão e link a confirmar ao baixar'
),
(
    'IN 75/2020',
    'ANVISA',
    NULL,
    NULL,
    NULL,
    NULL,
    'pendente_conferencia',
    'versão e link a confirmar ao baixar'
),
(
    'Tabela Brasileira de Composição de Alimentos (TACO)',
    'NEPA/Unicamp',
    NULL,
    NULL,
    NULL,
    NULL,
    'pendente_conferencia',
    'versão e link a confirmar ao baixar'
),
(
    'Diretrizes sobre açúcares e sódio',
    'OMS',
    NULL,
    NULL,
    NULL,
    NULL,
    'pendente_conferencia',
    'versão e link a confirmar ao baixar'
),
(
    'Diretrizes da Sociedade Brasileira de Diabetes (SBD)',
    'SBD',
    NULL,
    NULL,
    NULL,
    NULL,
    'pendente_conferencia',
    'versão e link a confirmar ao baixar'
)
ON CONFLICT (documento) DO NOTHING;
