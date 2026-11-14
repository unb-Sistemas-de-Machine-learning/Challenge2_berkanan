-- ============================================================================
-- ARQUIVO: migrations/002_taco_limites.sql
-- DESCRIÇÃO: Cria as tabelas taco_alimentos e limites_rotulagem, ambas com chave
--            estrangeira para fontes_documentos e padronizadas por 100 g/ml.
-- AUTOR: Davi Rodrigues (R4 Engenheiro de Dados) - Equipe Berkanan
-- DATA: 13/11/2026
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. TABELA: taco_alimentos
-- Feature Store relacional de alimentos da TACO (UNICAMP).
--
-- REGRA DE TRATAMENTO DE VALORES ESPECIAIS (NA e Tr):
-- 1. "NA" (Não Aplicável / Não Determinado): Armazenado como NULL. Indica ausência
--    de aferição em laboratório; não converter para 0.00.
-- 2. "Tr" (Traços): Armazenado como NULL na base física (teor detectado, porém
--    abaixo do limite de quantificação laboratorial).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS taco_alimentos (
    codigo_taco             VARCHAR(20) PRIMARY KEY,
    fonte_id                INTEGER NOT NULL REFERENCES fontes_documentos(id) ON UPDATE CASCADE,
    nome                    VARCHAR(255) NOT NULL,
    grupo                   VARCHAR(100) NOT NULL,
    
    -- Nutrientes normalizados estritamente por 100 g:
    energia_kcal            NUMERIC(8, 2) CHECK (energia_kcal IS NULL OR energia_kcal >= 0),
    energia_kj              NUMERIC(8, 2) CHECK (energia_kj IS NULL OR energia_kj >= 0),
    proteina_g              NUMERIC(8, 2) CHECK (proteina_g IS NULL OR proteina_g >= 0),
    lipidios_g              NUMERIC(8, 2) CHECK (lipidios_g IS NULL OR lipidios_g >= 0),
    saturados_g             NUMERIC(8, 2) CHECK (saturados_g IS NULL OR saturados_g >= 0),
    carboidrato_g           NUMERIC(8, 2) CHECK (carboidrato_g IS NULL OR carboidrato_g >= 0),
    fibra_g                 NUMERIC(8, 2) CHECK (fibra_g IS NULL OR fibra_g >= 0),
    sodio_mg                NUMERIC(8, 2) CHECK (sodio_mg IS NULL OR sodio_mg >= 0),
    
    atualizado_em           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- SUGESTÕES DO DAVI (NÃO APROVADAS PELO GRUPO - NÃO CONSTAM NO MATERIAL).
-- Ficam COMENTADAS até o grupo aprovar. Para ativar depois:
-- ALTER TABLE taco_alimentos ADD CONSTRAINT chk_taco_saturados_le_lipidios
--     CHECK (saturados_g IS NULL OR lipidios_g IS NULL OR saturados_g <= lipidios_g);
-- ALTER TABLE taco_alimentos ADD CONSTRAINT chk_taco_soma_macros_le_100
--     CHECK (carboidrato_g IS NULL OR proteina_g IS NULL OR lipidios_g IS NULL
--            OR (carboidrato_g + proteina_g + lipidios_g <= 100.00));
-- ----------------------------------------------------------------------------

-- NOTA DE CONSISTÊNCIA CALÓRICA (CONSTA NO CLAUDE.MD):
-- Relação aproximada de Atwater: energia ≈ 4×carboidratos + 4×proteínas + 9×gorduras

COMMENT ON TABLE taco_alimentos IS 'Composição centesimal de alimentos da TACO por 100 g com FK para fontes_documentos.';
COMMENT ON COLUMN taco_alimentos.fonte_id IS 'Chave estrangeira para o registro da TACO em fontes_documentos.';

CREATE INDEX IF NOT EXISTS idx_taco_alimentos_nome ON taco_alimentos (nome);
CREATE INDEX IF NOT EXISTS idx_taco_alimentos_grupo ON taco_alimentos (grupo);
CREATE INDEX IF NOT EXISTS idx_taco_alimentos_fonte ON taco_alimentos (fonte_id);


-- ----------------------------------------------------------------------------
-- 2. TABELA: limites_rotulagem
-- Parâmetros regulatórios de corte para a rotulagem frontal (lupas da IN 75/2020).
--
-- REGRA MANDATÓRIA (CLAUDE.MD):
-- A tabela deve permanecer rigorosamente VAZIA na inicialização.
-- NÃO PREENCHER LIMITES DE MEMÓRIA. Os valores oficiais vêm do texto da IN 75/2020.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS limites_rotulagem (
    id                      SERIAL PRIMARY KEY,
    fonte_id                INTEGER NOT NULL REFERENCES fontes_documentos(id) ON UPDATE CASCADE,
    norma                   VARCHAR(50) NOT NULL, -- ex: 'IN 75/2020'
    categoria               VARCHAR(20) NOT NULL CHECK (categoria IN ('sólido', 'líquido')),
    nutriente               VARCHAR(50) NOT NULL CHECK (nutriente IN ('açúcares adicionados', 'gorduras saturadas', 'sódio')),
    limite_100g             NUMERIC(8, 2) NOT NULL CHECK (limite_100g >= 0), -- Limite por 100 g ou 100 ml
    unidade                 VARCHAR(10) NOT NULL CHECK (unidade IN ('g', 'mg')),
    trecho_norma            TEXT NOT NULL, -- Transcrição literal do dispositivo de onde saiu o valor
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE limites_rotulagem IS 'Limites de rotulagem frontal (IN 75/2020) por 100 g/ml. Tabela mantida vazia: valores vêm do texto da IN 75/2020.';
COMMENT ON COLUMN limites_rotulagem.fonte_id IS 'Chave estrangeira para a IN 75/2020 em fontes_documentos (buscar o id pelo nome do documento).';

CREATE INDEX IF NOT EXISTS idx_limites_rotulagem_fonte ON limites_rotulagem (fonte_id);
CREATE INDEX IF NOT EXISTS idx_limites_rotulagem_lookup ON limites_rotulagem (categoria, nutriente);

-- ============================================================================
-- MODELO DE INSERT COMENTADO (NÃO EXECUTAR - VALORES VÊM DO TEXTO DA IN 75/2020):
--
-- INSERT INTO limites_rotulagem (fonte_id, norma, categoria, nutriente, limite_100g, unidade, trecho_norma)
-- VALUES (
--     (SELECT id FROM fontes_documentos WHERE documento = 'IN 75/2020'), -- id buscado pelo nome
--     'IN 75/2020',
--     'sólido',
--     'açúcares adicionados',
--     [VALOR: a copiar do texto da IN 75/2020],
--     'g',
--     '[TRECHO: a copiar do texto da IN 75/2020]'
-- );
-- ============================================================================
