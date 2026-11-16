-- ============================================================================
-- ARQUIVO: migrations/008_limites_in75.sql
-- DESCRIÇÃO: Preenche a tabela limites_rotulagem (6 registros: sólido/líquido
--            x açúcares adicionados, gorduras saturadas, sódio) com os valores
--            e o trecho literal do Anexo XV da IN nº 75/2020 (ANVISA).
--            Nota: A issue original citava 005_*.sql quando existiam apenas
--            001..004; seguindo a numeração sequencial do repositório após
--            005_atualiza_fontes.sql, 006_verificacao_links.sql e
--            007_carga_taco.sql, esta migração recebe o prefixo 008_.
-- FONTE: Instrução Normativa - IN nº 75, de 8/10/2020 (DOU nº 195, de
--        09/10/2020, Seção 1, pág. 113; Anexo XV, pág. 19 do PDF do DOU).
-- AUTOR: Davi Rodrigues (R4 Engenheiro de Dados) - Equipe Berkanan
-- ============================================================================

-- 1. Garante unicidade lógica (norma, categoria, nutriente) de forma idempotente
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_limites_rotulagem_norma_cat_nutr'
    ) THEN
        ALTER TABLE limites_rotulagem
            ADD CONSTRAINT uq_limites_rotulagem_norma_cat_nutr
            UNIQUE (norma, categoria, nutriente);
    END IF;
END $$;

-- 2. Carga idempotente dos 6 limites do Anexo XV da IN nº 75/2020
INSERT INTO limites_rotulagem (
    fonte_id,
    norma,
    categoria,
    nutriente,
    limite_100g,
    unidade,
    trecho_norma
)
SELECT
    f.id AS fonte_id,
    v.norma,
    v.categoria,
    v.nutriente,
    v.limite_100g,
    v.unidade,
    v.trecho_norma
FROM (
    VALUES
        (
            'IN 75/2020',
            'sólido',
            'açúcares adicionados',
            15.00::numeric(8,2),
            'g',
            'IN 75/2020, Anexo XV (Alimentos sólidos ou semissólidos): "Quantidade maior ou igual a 15 g de açúcares adicionados por 100 g do alimento."'
        ),
        (
            'IN 75/2020',
            'líquido',
            'açúcares adicionados',
            7.50::numeric(8,2),
            'g',
            'IN 75/2020, Anexo XV (Alimentos líquidos): "Quantidade maior ou igual a 7,5 g de açúcares adicionados por 100 ml do alimento."'
        ),
        (
            'IN 75/2020',
            'sólido',
            'gorduras saturadas',
            6.00::numeric(8,2),
            'g',
            'IN 75/2020, Anexo XV (Alimentos sólidos ou semissólidos): "Quantidade maior ou igual a 6 g de gorduras saturadas por 100 g do alimento."'
        ),
        (
            'IN 75/2020',
            'líquido',
            'gorduras saturadas',
            3.00::numeric(8,2),
            'g',
            'IN 75/2020, Anexo XV (Alimentos líquidos): "Quantidade maior ou igual a 3 g de gorduras saturadas por 100 ml do alimento."'
        ),
        (
            'IN 75/2020',
            'sólido',
            'sódio',
            600.00::numeric(8,2),
            'mg',
            'IN 75/2020, Anexo XV (Alimentos sólidos ou semissólidos): "Quantidade maior ou igual a 600 mg de sódio por 100 g do alimento."'
        ),
        (
            'IN 75/2020',
            'líquido',
            'sódio',
            300.00::numeric(8,2),
            'mg',
            'IN 75/2020, Anexo XV (Alimentos líquidos): "Quantidade maior ou igual a 300 mg de sódio por 100 ml do alimento."'
        )
) AS v(norma, categoria, nutriente, limite_100g, unidade, trecho_norma)
CROSS JOIN (
    SELECT id
    FROM fontes_documentos
    WHERE documento = 'IN 75/2020'
) AS f
ON CONFLICT (norma, categoria, nutriente) DO UPDATE SET
    fonte_id = EXCLUDED.fonte_id,
    limite_100g = EXCLUDED.limite_100g,
    unidade = EXCLUDED.unidade,
    trecho_norma = EXCLUDED.trecho_norma;
