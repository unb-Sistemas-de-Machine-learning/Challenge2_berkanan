-- ============================================================================
-- ARQUIVO: migrations/005_atualiza_fontes.sql
-- DESCRIÇÃO: Atualiza links, versões, data de download e observações de 4 fontes
--            oficiais conferidas pelo Davi em 16/11/2026.
--            Guia Alimentar e OMS não são alterados (permanecem a confirmar).
--            Adiciona constraint de integridade para status 'conferido' de forma
--            idempotente para bancos existentes.
-- AUTOR: Davi Rodrigues (R4 Engenheiro de Dados) - Equipe Berkanan
-- DATA: 16/11/2026
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. CONSTRAINT DE INTEGRIDADE IDEMPOTENTE
-- Garante que nenhuma fonte seja marcada como 'conferido' com dados incompletos.
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_fontes_conferido_completo'
    ) THEN
        ALTER TABLE fontes_documentos
            ADD CONSTRAINT chk_fontes_conferido_completo
            CHECK (status_conferencia <> 'conferido'
                   OR (data_download IS NOT NULL AND conferido_por IS NOT NULL
                       AND link IS NOT NULL AND versao IS NOT NULL));
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 2. ATUALIZAÇÕES IDEMPOTENTES DAS FONTES (DAVI - 16/11/2026)
-- Preenche apenas: versao, link, data_download e observacoes.
-- Não altera conferido_por nem status_conferencia.
-- ----------------------------------------------------------------------------

-- a) Tabela Brasileira de Composição de Alimentos (TACO)
UPDATE fontes_documentos
SET
    versao = '4ª ed. revisada e ampliada, NEPA/UNICAMP, 2011 (161 p.)',
    link = 'https://cfn.org.br/wp-content/uploads/2017/03/taco_4_edicao_ampliada_e_revisada.pdf',
    data_download = '2026-11-16',
    observacoes = 'Cópia hospedada pelo CFN; link antigo do NEPA fora do ar em 16/11/2026'
WHERE documento = 'Tabela Brasileira de Composição de Alimentos (TACO)';

-- b) Diretrizes da Sociedade Brasileira de Diabetes (SBD)
UPDATE fontes_documentos
SET
    versao = 'Cap. Terapia nutricional no pré-diabetes e no DM2, Diretriz SBD (DOI 10.29327/5238993.2023-8)',
    link = 'https://diretriz.diabetes.org.br/terapia-nutricional-no-pre-diabetes-e-no-diabetes-mellitus-tipo-2/',
    data_download = '2026-11-16',
    observacoes = 'Só este capítulo foi registrado; confirmar no repo do Desafio 1 quais documentos da SBD foram usados. O parâmetro ?cp_pdf=1 abre versão de impressão em HTML, não PDF.'
WHERE documento = 'Diretrizes da Sociedade Brasileira de Diabetes (SBD)';

-- c) RDC 429/2020
UPDATE fontes_documentos
SET
    versao = 'RDC nº 429, de 8/10/2020 (DOU nº 195, de 9/10/2020)',
    link = 'https://www.in.gov.br/en/web/dou/-/resolucao-de-diretoria-colegiada-rdc-n-429-de-8-de-outubro-de-2020-282070599',
    data_download = '2026-11-16',
    observacoes = 'Link do DOU informado pelo Davi (texto original). A RDC 819/2023 altera a RDC 429; conferir o texto com alterações antes de extrair limites.'
WHERE documento = 'RDC 429/2020';

-- d) IN 75/2020
UPDATE fontes_documentos
SET
    versao = 'IN nº 75, de 8/10/2020 (DOU nº 195, de 9/10/2020)',
    link = 'https://www.in.gov.br/en/web/dou/-/instrucao-normativa-in-n-75-de-8-de-outubro-de-2020-282071143',
    data_download = '2026-11-16',
    observacoes = 'Link do DOU informado pelo Davi. Os limites do "alto em" devem ser copiados do texto da norma, nunca de memória.'
WHERE documento = 'IN 75/2020';
