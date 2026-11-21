-- ============================================================================
-- MIGRAÇÃO 011: inclusão da RDC 727/2022 e da Lei 10.674/2003 (issues #20 e #27)
-- DATA: 21/11/2026 · Responsável: Davi Rodrigues (R4 — Engenheiro de Dados)
--
-- Registra em fontes_documentos as duas normas vigentes de rotulagem de
-- alergênicos, lactose e glúten aprovadas na decisão da issue #20 (17/11/2026):
--   1. RDC 727/2022 (ANVISA): arts. 13 e 14 ("ALÉRGICOS: CONTÉM" e "PODE CONTER"),
--      art. 18 ("CONTÉM LACTOSE" acima de 100 mg/100 g ou ml) e art. 40
--      (revogação da RDC 26/2015 e da RDC 136/2017).
--   2. Lei 10.674/2003 (Planalto): art. 1º ("contém Glúten" / "não contém Glúten").
--
-- Não edita migrações anteriores. Idempotente (ON CONFLICT DO UPDATE).
-- ============================================================================

INSERT INTO fontes_documentos (
    documento,
    orgao,
    versao,
    link,
    data_download,
    link_verificado_em,
    link_verificado_por,
    conferido_por,
    status_conferencia,
    observacoes
) VALUES
(
    'RDC 727/2022',
    'ANVISA',
    'RDC nº 727, de 1º de julho de 2022 (DOU de 06/07/2022, em vigor desde 01/09/2022)',
    'https://www.in.gov.br/en/web/dou/-/resolucao-rdc-n-727-de-1-de-julho-de-2022-413249279',
    DATE '2026-11-21',
    DATE '2026-11-21',
    'Davi Rodrigues (R4)',
    'Davi Rodrigues (R4)',
    'conferido',
    'Incluída pela decisão da issue #20 (17/11/2026). Texto extraído do HTML oficial do DOU; conferidos arts. 13 e 14 (ALÉRGICOS: CONTÉM / PODE CONTER), art. 18 (CONTÉM LACTOSE > 100 mg/100 g ou ml) e art. 40 (revogações).'
),
(
    'Lei 10.674/2003',
    'Presidência da República / Casa Civil',
    'Lei nº 10.674, de 16 de maio de 2003 (DOU de 19/05/2003)',
    'https://www.planalto.gov.br/ccivil_03/leis/2003/l10.674.htm',
    DATE '2026-11-21',
    DATE '2026-11-21',
    'Davi Rodrigues (R4)',
    'Davi Rodrigues (R4)',
    'conferido',
    'Incluída pela decisão da issue #20 (17/11/2026). Texto extraído do HTML oficial do Planalto; conferido art. 1º (obrigatoriedade das inscrições "contém Glúten" ou "não contém Glúten").'
)
ON CONFLICT (documento) DO UPDATE SET
    orgao = EXCLUDED.orgao,
    versao = EXCLUDED.versao,
    link = EXCLUDED.link,
    data_download = COALESCE(fontes_documentos.data_download, EXCLUDED.data_download),
    link_verificado_em = COALESCE(fontes_documentos.link_verificado_em, EXCLUDED.link_verificado_em),
    link_verificado_por = COALESCE(fontes_documentos.link_verificado_por, EXCLUDED.link_verificado_por),
    conferido_por = COALESCE(fontes_documentos.conferido_por, EXCLUDED.conferido_por),
    status_conferencia = EXCLUDED.status_conferencia,
    observacoes = EXCLUDED.observacoes;
