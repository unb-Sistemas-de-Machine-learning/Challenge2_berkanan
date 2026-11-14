-- ============================================================================
-- ARQUIVO: seed_exemplo.sql
-- DESCRIÇÃO: Insere exatamente 2 linhas de exemplo na tabela taco_alimentos
--            com dados e valores claramente fictícios, exclusivamente para
--            destravar o desenvolvimento do João Victor, Carlos e Gustavo.
-- AUTOR: Davi Rodrigues (R4 Engenheiro de Dados) - Equipe Berkanan
-- DATA: 13/11/2026
-- REVISÃO 14/11: fica em seeds/ (fora de migrations/) para não entrar em
--            produção; o fonte_id é buscado pelo nome (antes apontava para a IN 75).
-- USO (só em dev): SEED=1 ./migrations/migrate.sh
-- ============================================================================

INSERT INTO taco_alimentos (
    codigo_taco,
    fonte_id,
    nome,
    grupo,
    energia_kcal,
    energia_kj,
    proteina_g,
    lipidios_g,
    saturados_g,
    carboidrato_g,
    fibra_g,
    sodio_mg
) VALUES 
(
    'EXEMPLO_01',
    (SELECT id FROM fontes_documentos WHERE documento = 'Tabela Brasileira de Composição de Alimentos (TACO)'),
    '[EXEMPLO FICTÍCIO] Alimento Teste A (Cereal em Flocos)',
    'Cereais e derivados',
    130.00,
    544.00,
    2.60,
    0.40,
    0.10,
    28.20,
    1.40,
    1.00
),
(
    'EXEMPLO_02',
    (SELECT id FROM fontes_documentos WHERE documento = 'Tabela Brasileira de Composição de Alimentos (TACO)'),
    '[EXEMPLO FICTÍCIO] Alimento Teste B (Feijão Cozido)',
    'Leguminosas e derivados',
    76.00,
    318.00,
    4.80,
    0.50,
    NULL, -- Campo nulo demonstrando regra formal de tratamento para NA/Tr
    13.60,
    8.50,
    2.00
)
ON CONFLICT (codigo_taco) DO NOTHING;
