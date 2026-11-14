-- ============================================================================
-- ARQUIVO: migrations/003_cache.sql
-- DESCRIÇÃO: Cria a tabela produtos_lidos com campos normalizados por 100 g/ml,
--            porção, JSONB para porção e %VD, alergênicos, checagem aprovada do CLAUDE.md,
--            Regra nº 6 e conformidade com a LGPD.
-- AUTOR: Davi Rodrigues (R4 Engenheiro de Dados) - Equipe Berkanan
-- DATA: 13/11/2026
-- ============================================================================

CREATE TABLE IF NOT EXISTS produtos_lidos (
    id                          BIGSERIAL PRIMARY KEY,
    
    -- Hash único para cache (SUGESTÃO do Davi: formato SHA-256 não consta no material):
    hash_rotulo                 VARCHAR(64) NOT NULL UNIQUE,
    
    nome_produto                VARCHAR(255),
    categoria                   VARCHAR(20) CHECK (categoria IS NULL OR categoria IN ('sólido', 'líquido')),
    
    -- Declaração da porção de referência do rótulo:
    porcao_quantidade           NUMERIC(8, 2) CHECK (porcao_quantidade IS NULL OR porcao_quantidade > 0),
    porcao_unidade              VARCHAR(20), -- ex: 'g', 'ml', 'unidade'
    
    -- Campos nutricionais normalizados estritamente por 100 g ou 100 ml:
    energia_kcal_100g           NUMERIC(8, 2) CHECK (energia_kcal_100g IS NULL OR energia_kcal_100g >= 0),
    carboidrato_100g            NUMERIC(8, 2) CHECK (carboidrato_100g IS NULL OR carboidrato_100g >= 0),
    acucares_totais_100g        NUMERIC(8, 2) CHECK (acucares_totais_100g IS NULL OR acucares_totais_100g >= 0),
    acucares_adicionados_100g   NUMERIC(8, 2) CHECK (acucares_adicionados_100g IS NULL OR acucares_adicionados_100g >= 0),
    proteina_100g               NUMERIC(8, 2) CHECK (proteina_100g IS NULL OR proteina_100g >= 0),
    gorduras_totais_100g        NUMERIC(8, 2) CHECK (gorduras_totais_100g IS NULL OR gorduras_totais_100g >= 0),
    gorduras_saturadas_100g     NUMERIC(8, 2) CHECK (gorduras_saturadas_100g IS NULL OR gorduras_saturadas_100g >= 0),
    gorduras_trans_100g         NUMERIC(8, 2) CHECK (gorduras_trans_100g IS NULL OR gorduras_trans_100g >= 0),
    fibra_100g                  NUMERIC(8, 2) CHECK (fibra_100g IS NULL OR fibra_100g >= 0),
    sodio_100g                  NUMERIC(8, 2) CHECK (sodio_100g IS NULL OR sodio_100g >= 0), -- mg por 100 g/ml

    -- Valores originais declarados por porção e percentual de valores diários (%VD) em JSONB:
    valores_porcao_jsonb        JSONB NOT NULL DEFAULT '{}'::jsonb,
    percentual_vd_jsonb         JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Alergênicos:
    alergenicos_texto_bruto     TEXT, -- texto lido da linha "ALÉRGICOS"
    alergenicos_extraidos       JSONB NOT NULL DEFAULT '[]'::jsonb, -- lista extraída

    -- Metadados técnicos do pipeline:
    metodo_extracao             VARCHAR(50) NOT NULL,
    versao_regras               VARCHAR(20) NOT NULL,
    confirmado_usuario          BOOLEAN NOT NULL DEFAULT FALSE,
    criado_em                   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- ------------------------------------------------------------------------
    -- CHECK DE CONSISTÊNCIA APROVADO (CLAUDE.md, Seção 5.2):
    -- ------------------------------------------------------------------------
    -- Açúcares totais <= carboidratos:
    CONSTRAINT chk_prod_acucares_totais_le_carbo
        CHECK (acucares_totais_100g IS NULL OR carboidrato_100g IS NULL 
               OR acucares_totais_100g <= carboidrato_100g)
);

-- NOTA DE CONSISTÊNCIA CALÓRICA (CONSTA NO CLAUDE.MD, Seção 5.2):
-- Relação aproximada de Atwater: energia ≈ 4×carboidratos + 4×proteínas + 9×gorduras
-- (checagem aproximada: fica no código de extração, não como CHECK do banco).

-- ----------------------------------------------------------------------------
-- SUGESTÕES DO DAVI (NÃO APROVADAS PELO GRUPO - NÃO CONSTAM NO MATERIAL).
-- Ficam COMENTADAS até o grupo aprovar. Para ativar depois:
-- ALTER TABLE produtos_lidos ADD CONSTRAINT chk_prod_acucares_adic_le_totais
--     CHECK (acucares_adicionados_100g IS NULL OR acucares_totais_100g IS NULL
--            OR acucares_adicionados_100g <= acucares_totais_100g);
-- ALTER TABLE produtos_lidos ADD CONSTRAINT chk_prod_gord_sat_le_totais
--     CHECK (gorduras_saturadas_100g IS NULL OR gorduras_totais_100g IS NULL
--            OR gorduras_saturadas_100g <= gorduras_totais_100g);
-- ALTER TABLE produtos_lidos ADD CONSTRAINT chk_prod_gord_trans_le_totais
--     CHECK (gorduras_trans_100g IS NULL OR gorduras_totais_100g IS NULL
--            OR gorduras_trans_100g <= gorduras_totais_100g);
-- ALTER TABLE produtos_lidos ADD CONSTRAINT chk_prod_soma_macros_le_100
--     CHECK (carboidrato_100g IS NULL OR proteina_100g IS NULL OR gorduras_totais_100g IS NULL
--            OR (carboidrato_100g + proteina_100g + gorduras_totais_100g <= 100.00));
-- ALTER TABLE produtos_lidos ADD CONSTRAINT chk_prod_energia_max
--     CHECK (energia_kcal_100g IS NULL OR energia_kcal_100g <= 900.00);
-- ----------------------------------------------------------------------------

-- ============================================================================
-- REGRAS MANDATÓRIAS DO CLAUDE.MD:
-- 1. REGRA APROVADA Nº 6:
--    NUNCA criar campo nem lógica que afirme "livre de alergênicos".
-- 2. LGPD:
--    Sem fotos nem perfil de saúde sem consentimento do usuário.
-- ============================================================================

COMMENT ON TABLE produtos_lidos IS 'Cache de produtos lidos. Regra nº 6: NUNCA afirmar livre de alergênicos. LGPD: sem fotos nem perfil de saúde sem consentimento.';
COMMENT ON COLUMN produtos_lidos.hash_rotulo IS 'Hash único do rótulo para deduplicação.';
COMMENT ON COLUMN produtos_lidos.valores_porcao_jsonb IS 'Valores originais por porção em JSONB.';
COMMENT ON COLUMN produtos_lidos.percentual_vd_jsonb IS '%VD em JSONB.';
COMMENT ON COLUMN produtos_lidos.alergenicos_texto_bruto IS 'Texto lido da linha ALÉRGICOS.';
COMMENT ON COLUMN produtos_lidos.alergenicos_extraidos IS 'Lista extraída de substâncias alergênicas detectadas. NUNCA deduz ausência.';

CREATE INDEX IF NOT EXISTS idx_produtos_lidos_hash ON produtos_lidos (hash_rotulo);
CREATE INDEX IF NOT EXISTS idx_produtos_lidos_nome ON produtos_lidos (nome_produto);
CREATE INDEX IF NOT EXISTS idx_produtos_lidos_versao ON produtos_lidos (versao_regras);
CREATE INDEX IF NOT EXISTS idx_produtos_lidos_alergenicos ON produtos_lidos USING gin (alergenicos_extraidos);
