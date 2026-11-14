-- ============================================================================
-- ARQUIVO: migrations/004_metricas.sql
-- DESCRIÇÃO: Cria a tabela metricas_requisicao e as views analíticas por consulta SQL
--            cobrindo todas as 10 métricas de validação, benchmark e monitoramento
--            aprovadas no CLAUDE.md (Seções 5.6, 9, 9.1 e 9.2).
--
-- DIRETRIZES DO CLAUDE.MD:
-- 1. Monitoramento no PostgreSQL (uma linha por requisição).
-- 2. Checagem de limiares por consultas SQL (acerto < 85% ou fidelidade < 90%), sem alertas.
--    REVISÃO 14/11: views mostram NULL / 'Sem dados' quando não há linhas.
-- 3. Benchmark RAG x LLM puro (acerto RAG >= 15 pontos acima do LLM puro).
-- 4. Benchmark Verificador A/B/C (C só fica se ganhar >= 5 pontos sobre B com <= 3 s a mais).
-- 5. Benchmark OCR (Tesseract vs PaddleOCR vs Gemini; acerto >= 85%; tempo e custo).
-- 6. Métricas por categoria do conjunto de teste (Prefixos A a G da Seção 9.1).
-- 7. Avaliação de usuários (nota média >= 4 de 5).
-- 8. Sem Prometheus; sem alertas em tempo real.
--
-- AUTOR: Davi Rodrigues (R4 Engenheiro de Dados) - Equipe Berkanan
-- DATA: 13/11/2026
-- ============================================================================

CREATE TABLE IF NOT EXISTS metricas_requisicao (
    id                          BIGSERIAL PRIMARY KEY,
    timestamp_requisicao        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tipo_operacao               VARCHAR(50) NOT NULL, -- 'extracao_ocr', 'chat_nutricional', 'comparacao_produtos', 'benchmark'
    
    -- Configuração do fluxo e teste (CLAUDE.md Seção 5.4, 9, 9.1):
    modo_execucao               VARCHAR(20) DEFAULT 'rag' CHECK (modo_execucao IN ('rag', 'llm_puro')),
    categoria_teste             VARCHAR(50), -- 'A_guia_alimentar', 'B_rotulagem_anvisa', 'C_calculo_alto_em', 'D_comparacao_produtos', 'E_alergenicos', 'F_saude_oms', 'G_fora_do_escopo'
    id_questao_teste            VARCHAR(20), -- 'A01'..'A10', 'B01'..'B10', 'C01'..'C08', 'D01'..'D06', 'E01'..'E05', 'F01'..'F05', 'G01'..'G06'
    configuracao_verificador    VARCHAR(10) CHECK (configuracao_verificador IN ('A', 'B', 'C')), -- A: sem, B: regras, C: LLM
    versao_ocr                  VARCHAR(50), -- 'tesseract', 'paddleocr', 'apenas_llm', 'nenhum'
    modelo_usado                VARCHAR(50) NOT NULL, -- 'gemini', 'modelo_alternativo', 'regras'

    -- Telemetria básica operacional (CLAUDE.md Seção 5.6):
    latencia_ms                 INTEGER NOT NULL CHECK (latencia_ms >= 0),
    falha_leitura               BOOLEAN NOT NULL DEFAULT FALSE,
    tipo_falha                  VARCHAR(100), -- 'ocr_ilegivel', 'violacao_consistencia', 'timeout', etc.
    chamadas_llm                INTEGER NOT NULL DEFAULT 0 CHECK (chamadas_llm >= 0), -- meta: média <= 2 por resposta

    -- Métricas de validação e qualidade (CLAUDE.md Seção 9 e 9.2):
    acerto                      BOOLEAN, -- acerto frente ao gabarito / campos lidos (meta: >= 85%)
    fidelidade_pct              NUMERIC(5, 2) CHECK (fidelidade_pct IS NULL OR (fidelidade_pct >= 0 AND fidelidade_pct <= 100)), -- afirmações sustentadas pela fonte (meta: >= 90%)
    recall_top3                 BOOLEAN, -- trecho certo entre os 3 primeiros recuperados (meta: >= 80%)
    recusa_correta              BOOLEAN, -- respondeu "não há evidência suficiente" quando fora da base (meta: >= 90%)
    
    -- Custo e avaliação de usuários (CLAUDE.md Seção 9):
    custo_estimado_usd          NUMERIC(8, 5) CHECK (custo_estimado_usd IS NULL OR custo_estimado_usd >= 0), -- comparativo Tesseract, PaddleOCR, Gemini
    avaliacao_usuario_nota      INTEGER CHECK (avaliacao_usuario_nota IS NULL OR (avaliacao_usuario_nota >= 1 AND avaliacao_usuario_nota <= 5)) -- nota de 1 a 5 (meta: >= 4 de 5)
);

COMMENT ON TABLE metricas_requisicao IS 'Telemetria e métricas de validação do Desafio 2 no PostgreSQL. Sem Prometheus/alertas.';
COMMENT ON COLUMN metricas_requisicao.modo_execucao IS 'Identifica se a requisição rodou com RAG ou com LLM puro para a métrica da semana 2.';
COMMENT ON COLUMN metricas_requisicao.categoria_teste IS 'Categoria do conjunto de teste (A até G conforme Seção 9.1 do CLAUDE.md).';
COMMENT ON COLUMN metricas_requisicao.configuracao_verificador IS 'Configuração do teste: A (sem verificador), B (por regras), C (agente com LLM).';
COMMENT ON COLUMN metricas_requisicao.falha_leitura IS 'True se o processamento do rótulo falhou ou violou restrições de consistência.';
COMMENT ON COLUMN metricas_requisicao.acerto IS 'Acerto frente ao gabarito ou extração correta de campos da foto.';
COMMENT ON COLUMN metricas_requisicao.fidelidade_pct IS 'Percentual de afirmações sustentadas pelo trecho citado do RAG.';
COMMENT ON COLUMN metricas_requisicao.recusa_correta IS 'Recusa com não há evidência suficiente para temas fora do escopo.';

CREATE INDEX IF NOT EXISTS idx_metricas_timestamp ON metricas_requisicao (timestamp_requisicao);
CREATE INDEX IF NOT EXISTS idx_metricas_operacao ON metricas_requisicao (tipo_operacao);
CREATE INDEX IF NOT EXISTS idx_metricas_verificador ON metricas_requisicao (configuracao_verificador);
CREATE INDEX IF NOT EXISTS idx_metricas_modo_execucao ON metricas_requisicao (modo_execucao);
CREATE INDEX IF NOT EXISTS idx_metricas_categoria_teste ON metricas_requisicao (categoria_teste);
CREATE INDEX IF NOT EXISTS idx_metricas_falha ON metricas_requisicao (falha_leitura);


-- ============================================================================
-- VIEW 1: vw_metricas_agregadas_diarias (CLAUDE.md Seção 5.6)
-- Agregação diária operacional: latência mediana, chamadas LLM e taxa de falhas.
-- ============================================================================
CREATE OR REPLACE VIEW vw_metricas_agregadas_diarias AS
SELECT
    DATE(timestamp_requisicao)                                          AS data_referencia,
    tipo_operacao,
    COALESCE(configuracao_verificador, 'N/A')                           AS configuracao_verificador,
    COUNT(*)                                                            AS total_requisicoes,
    ROUND(
        percentile_cont(0.5) WITHIN GROUP (ORDER BY latencia_ms)::numeric, 
        2
    )                                                                   AS latencia_mediana_ms,
    ROUND(AVG(chamadas_llm), 2)                                         AS media_chamadas_llm,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE falha_leitura IS TRUE) / COUNT(*), 
        2
    )                                                                   AS taxa_falha_leitura_pct
FROM metricas_requisicao
GROUP BY
    DATE(timestamp_requisicao),
    tipo_operacao,
    configuracao_verificador;

COMMENT ON VIEW vw_metricas_agregadas_diarias IS 'Agregação diária operacional para monitoramento do sistema no PostgreSQL.';


-- ============================================================================
-- VIEW 2: vw_checagem_limiares_monitoramento
-- Checagem por consulta SQL direta (sem alertas automáticos, decisão de 13/11):
-- - Limiar aprovado (CLAUDE.md Seção 5.6): acerto < 85% ou fidelidade < 90%
-- - Metas de validação (CLAUDE.md Seção 9): tempo de resposta > 10 s (10.000 ms)
--   no 4G e média de chamadas ao LLM > 2 por resposta
-- Colunas de violação ficam NULL quando não há dados.
-- ============================================================================
CREATE OR REPLACE VIEW vw_checagem_limiares_monitoramento AS
SELECT
    DATE(timestamp_requisicao)                                          AS data_referencia,
    tipo_operacao,
    COUNT(*)                                                            AS total_amostras,
    
    -- 1. Métrica de Acerto (Meta: >= 85%)
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE acerto IS TRUE) / 
        NULLIF(COUNT(*) FILTER (WHERE acerto IS NOT NULL), 0),
        2
    )                                                                   AS taxa_acerto_pct,
    ((100.0 * COUNT(*) FILTER (WHERE acerto IS TRUE) / 
              NULLIF(COUNT(*) FILTER (WHERE acerto IS NOT NULL), 0)) < 85.0)                                                                 AS violou_limiar_acerto_85,  -- NULL quando não há dados

    -- 2. Métrica de Fidelidade (Meta: >= 90%)
    ROUND(AVG(fidelidade_pct), 2)                                       AS fidelidade_media_pct,
    (AVG(fidelidade_pct) < 90.0)                                                                 AS violou_limiar_fidelidade_90,  -- NULL quando não há dados

    -- 3. Tempo de Resposta (Meta: mediana <= 10 s / 10.000 ms)
    ROUND(
        percentile_cont(0.5) WITHIN GROUP (ORDER BY latencia_ms)::numeric, 
        2
    )                                                                   AS latencia_mediana_ms,
    (percentile_cont(0.5) WITHIN GROUP (ORDER BY latencia_ms) > 10000)                                                                 AS violou_limiar_tempo_10s,  -- NULL quando não há dados

    -- 4. Chamadas ao LLM (Meta: média <= 2)
    ROUND(AVG(chamadas_llm), 2)                                         AS media_chamadas_llm,
    (AVG(chamadas_llm) > 2.0)                                                                 AS violou_limiar_chamadas_llm_2  -- NULL quando não há dados

FROM metricas_requisicao
GROUP BY
    DATE(timestamp_requisicao),
    tipo_operacao;

COMMENT ON VIEW vw_checagem_limiares_monitoramento IS 'Checagem por SQL, sem alertas: limiar aprovado (acerto < 85%, fidelidade < 90%, Seção 5.6) e metas da Seção 9 (tempo > 10 s, chamadas > 2).';


-- ============================================================================
-- VIEW 3: vw_benchmark_rag_vs_llm_puro (CLAUDE.md Seção 9 - Métrica 1)
-- Compara a acurácia de respostas do RAG vs LLM puro.
-- Meta aprovada: RAG >= 15 pontos percentuais acima do LLM puro.
-- ============================================================================
CREATE OR REPLACE VIEW vw_benchmark_rag_vs_llm_puro AS
WITH metricas_por_modo AS (
    SELECT
        COUNT(*) FILTER (WHERE modo_execucao = 'llm_puro')              AS total_llm_puro,
        ROUND(
            100.0 * COUNT(*) FILTER (WHERE modo_execucao = 'llm_puro' AND acerto IS TRUE) / 
            NULLIF(COUNT(*) FILTER (WHERE modo_execucao = 'llm_puro' AND acerto IS NOT NULL), 0),
            2
        )                                                               AS acerto_llm_puro_pct,
        COUNT(*) FILTER (WHERE modo_execucao = 'rag')                   AS total_rag,
        ROUND(
            100.0 * COUNT(*) FILTER (WHERE modo_execucao = 'rag' AND acerto IS TRUE) / 
            NULLIF(COUNT(*) FILTER (WHERE modo_execucao = 'rag' AND acerto IS NOT NULL), 0),
            2
        )                                                               AS acerto_rag_pct
    FROM metricas_requisicao
    WHERE modo_execucao IN ('rag', 'llm_puro')
)
SELECT
    total_llm_puro,
    acerto_llm_puro_pct,
    total_rag,
    acerto_rag_pct,
    ROUND((acerto_rag_pct - acerto_llm_puro_pct)::numeric, 2)           AS ganho_pontos_rag_vs_llm,
    ((acerto_rag_pct - acerto_llm_puro_pct) >= 15.0)                                                                 AS meta_15_pontos_atingida  -- NULL quando não há dados
FROM metricas_por_modo;

COMMENT ON VIEW vw_benchmark_rag_vs_llm_puro IS 'Comparativo RAG vs LLM puro. Meta aprovada: RAG >= 15 pontos acima do LLM puro.';


-- ============================================================================
-- VIEW 4: vw_benchmark_verificador_abc (CLAUDE.md Seção 9.2)
-- Relatório comparativo das configurações A, B e C para o Gustavo (R3 Cientista de dados):
-- - Config A: Sem verificador
-- - Config B: Verificação por regras (sem LLM)
-- - Config C: Verificador com LLM
-- ============================================================================
CREATE OR REPLACE VIEW vw_benchmark_verificador_abc AS
SELECT
    configuracao_verificador,
    COUNT(*)                                                            AS total_questoes_avaliadas,
    
    -- Fidelidade às fontes (meta: >= 90%)
    ROUND(AVG(fidelidade_pct), 2)                                       AS fidelidade_media_pct,
    
    -- Acerto frente ao gabarito
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE acerto IS TRUE) / 
        NULLIF(COUNT(*) FILTER (WHERE acerto IS NOT NULL), 0),
        2
    )                                                                   AS taxa_acerto_pct,
    
    -- Recusa correta (meta: >= 90% para perguntas fora da base)
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE recusa_correta IS TRUE) / 
        NULLIF(COUNT(*) FILTER (WHERE recusa_correta IS NOT NULL), 0),
        2
    )                                                                   AS taxa_recusa_correta_pct,
    
    -- Recall top 3 (meta: >= 80%)
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE recall_top3 IS TRUE) / 
        NULLIF(COUNT(*) FILTER (WHERE recall_top3 IS NOT NULL), 0),
        2
    )                                                                   AS recall_top3_pct,
    
    -- Latência mediana em ms
    ROUND(
        percentile_cont(0.5) WITHIN GROUP (ORDER BY latencia_ms)::numeric, 
        2
    )                                                                   AS latencia_mediana_ms,
    
    -- Média de chamadas ao LLM
    ROUND(AVG(chamadas_llm), 2)                                         AS media_chamadas_llm
FROM metricas_requisicao
WHERE configuracao_verificador IS NOT NULL
GROUP BY configuracao_verificador
ORDER BY configuracao_verificador;

COMMENT ON VIEW vw_benchmark_verificador_abc IS 'Tabela comparativa do benchmark do verificador A/B/C conforme Seção 9.2 do CLAUDE.md.';


-- ============================================================================
-- VIEW 5: vw_decisao_verificador_c_vs_b (CLAUDE.md Seção 5.4 e 9.2)
-- Regra aprovada: O verificador C (com LLM) só fica se ganhar >= 5 pontos de
-- fidelidade sobre B (por regras) com acréscimo de latência <= 3 s (3000 ms).
-- ============================================================================
CREATE OR REPLACE VIEW vw_decisao_verificador_c_vs_b AS
WITH dados_b AS (
    SELECT
        ROUND(AVG(fidelidade_pct), 2)                                   AS fidelidade_b,
        ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY latencia_ms)::numeric, 2) AS latencia_mediana_b_ms
    FROM metricas_requisicao
    WHERE configuracao_verificador = 'B'
),
dados_c AS (
    SELECT
        ROUND(AVG(fidelidade_pct), 2)                                   AS fidelidade_c,
        ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY latencia_ms)::numeric, 2) AS latencia_mediana_c_ms
    FROM metricas_requisicao
    WHERE configuracao_verificador = 'C'
)
SELECT
    b.fidelidade_b                                                      AS fidelidade_b_pct,
    c.fidelidade_c                                                      AS fidelidade_c_pct,
    ROUND((c.fidelidade_c - b.fidelidade_b)::numeric, 2)                AS ganho_fidelidade_c_vs_b_pct,
    b.latencia_mediana_b_ms,
    c.latencia_mediana_c_ms,
    ROUND((c.latencia_mediana_c_ms - b.latencia_mediana_b_ms)::numeric, 2) AS diferenca_latencia_ms,
    ((c.fidelidade_c - b.fidelidade_b) >= 5.0)                                                                 AS criterio_fidelidade_5pts_ok,  -- NULL quando não há dados
    ((c.latencia_mediana_c_ms - b.latencia_mediana_b_ms) <= 3000.0)                                                                 AS criterio_latencia_3s_ok,  -- NULL quando não há dados
    CASE 
        WHEN b.fidelidade_b IS NULL OR c.fidelidade_c IS NULL
          OR b.latencia_mediana_b_ms IS NULL OR c.latencia_mediana_c_ms IS NULL
        THEN 'SEM_DADOS (aguardando benchmark de B e C)'
        WHEN (c.fidelidade_c - b.fidelidade_b) >= 5.0 
         AND (c.latencia_mediana_c_ms - b.latencia_mediana_b_ms) <= 3000.0 
        THEN 'MANTER_CONFIG_C (Verificador LLM aprovado)'
        ELSE 'MANTER_CONFIG_B (Verificador por regras adotado)'
    END                                                                 AS decisao_arquitetural_final
FROM dados_b b, dados_c c;

COMMENT ON VIEW vw_decisao_verificador_c_vs_b IS 'Aplicação automática da regra de corte: C só fica se fidelidade >= +5 pts e latência <= +3s.';


-- ============================================================================
-- VIEW 6: vw_benchmark_extracao_ocr (CLAUDE.md Seção 9 - Métricas 6 e 7)
-- Comparativo Tesseract vs PaddleOCR vs Gemini para acerto da extração e custo.
-- Meta aprovada: acerto da extração >= 85% de campos lidos corretamente.
-- ============================================================================
CREATE OR REPLACE VIEW vw_benchmark_extracao_ocr AS
SELECT
    COALESCE(versao_ocr, 'apenas_llm')                                  AS motor_ocr,
    modelo_usado,
    COUNT(*)                                                            AS total_fotos_processadas,
    
    -- Acerto da extração (meta: >= 85%)
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE acerto IS TRUE) / 
        NULLIF(COUNT(*) FILTER (WHERE acerto IS NOT NULL), 0),
        2
    )                                                                   AS taxa_acerto_extracao_pct,
    ((100.0 * COUNT(*) FILTER (WHERE acerto IS TRUE) / 
              NULLIF(COUNT(*) FILTER (WHERE acerto IS NOT NULL), 0)) >= 85.0)                                                                 AS meta_acerto_85_atingida,  -- NULL quando não há dados
    
    -- Taxa de falhas de leitura
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE falha_leitura IS TRUE) / COUNT(*),
        2
    )                                                                   AS taxa_falhas_pct,
    
    -- Latência mediana por foto
    ROUND(
        percentile_cont(0.5) WITHIN GROUP (ORDER BY latencia_ms)::numeric, 
        2
    )                                                                   AS latencia_mediana_ms,
    
    -- Custo médio estimado por foto
    ROUND(AVG(custo_estimado_usd), 5)                                   AS custo_medio_foto_usd
FROM metricas_requisicao
WHERE tipo_operacao = 'extracao_ocr'
GROUP BY
    versao_ocr,
    modelo_usado;

COMMENT ON VIEW vw_benchmark_extracao_ocr IS 'Comparativo de métodos de extração OCR (Tesseract, PaddleOCR, Gemini) da Semana 4.';


-- ============================================================================
-- VIEW 7: vw_metricas_por_categoria_teste (CLAUDE.md Seção 9.1)
-- Avaliação detalhada do conjunto de 50 questões por categoria (Prefixos A a G):
-- A: Guia Alimentar (10) | B: ANVISA (10) | C: Cálculo ALTO EM (8)
-- D: Comparação (6)      | E: Alergênicos (5) | F: Saúde e OMS (5)
-- G: Fora do escopo (6)
-- ============================================================================
CREATE OR REPLACE VIEW vw_metricas_por_categoria_teste AS
SELECT
    categoria_teste,
    COUNT(*)                                                            AS total_questoes,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE acerto IS TRUE) / 
        NULLIF(COUNT(*) FILTER (WHERE acerto IS NOT NULL), 0),
        2
    )                                                                   AS taxa_acerto_pct,
    ROUND(AVG(fidelidade_pct), 2)                                       AS fidelidade_media_pct,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE recall_top3 IS TRUE) / 
        NULLIF(COUNT(*) FILTER (WHERE recall_top3 IS NOT NULL), 0),
        2
    )                                                                   AS recall_top3_pct,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE recusa_correta IS TRUE) / 
        NULLIF(COUNT(*) FILTER (WHERE recusa_correta IS NOT NULL), 0),
        2
    )                                                                   AS taxa_recusa_correta_pct,
    ROUND(
        percentile_cont(0.5) WITHIN GROUP (ORDER BY latencia_ms)::numeric, 
        2
    )                                                                   AS latencia_mediana_ms
FROM metricas_requisicao
WHERE categoria_teste IS NOT NULL
GROUP BY categoria_teste
ORDER BY categoria_teste;

COMMENT ON VIEW vw_metricas_por_categoria_teste IS 'Consolidação das métricas pelas 7 categorias do conjunto de teste (A até G).';


-- ============================================================================
-- VIEW 8: vw_avaliacao_usuarios (CLAUDE.md Seção 9 - Métrica 10)
-- Avaliação de clareza e utilidade com 5 a 10 pessoas (Semana 6).
-- Meta aprovada: nota média >= 4 de 5.
-- ============================================================================
CREATE OR REPLACE VIEW vw_avaliacao_usuarios AS
SELECT
    COUNT(*)                                                            AS total_avaliacoes,
    ROUND(AVG(avaliacao_usuario_nota), 2)                               AS nota_media_geral,
    COUNT(*) FILTER (WHERE avaliacao_usuario_nota = 5)                  AS total_nota_5,
    COUNT(*) FILTER (WHERE avaliacao_usuario_nota = 4)                  AS total_nota_4,
    COUNT(*) FILTER (WHERE avaliacao_usuario_nota = 3)                  AS total_nota_3,
    COUNT(*) FILTER (WHERE avaliacao_usuario_nota <= 2)                 AS total_nota_baixa_1_2,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE avaliacao_usuario_nota >= 4) / NULLIF(COUNT(*), 0),
        2
    )                                                                   AS satisfacao_nota_4_ou_5_pct,
    (AVG(avaliacao_usuario_nota) >= 4.0)                                                                 AS meta_nota_4_atingida  -- NULL quando não há dados
FROM metricas_requisicao
WHERE avaliacao_usuario_nota IS NOT NULL;

COMMENT ON VIEW vw_avaliacao_usuarios IS 'Consolidação da avaliação qualitativa de usuários (nota 1 a 5). Meta: média >= 4.';


-- ============================================================================
-- VIEW 9: vw_painel_consolidado_10_metricas (CLAUDE.md Seção 9)
-- Painel geral sumarizando as 10 métricas oficiais do projeto para relatórios.
-- ============================================================================
CREATE OR REPLACE VIEW vw_painel_consolidado_10_metricas AS
SELECT
    1 AS id_metrica,
    'Acerto das respostas'::varchar(50)                                 AS metrica,
    'RAG >= 15 pontos acima do LLM puro'::varchar(60)                   AS meta_aprovada,
    'Semana 2'::varchar(20)                                             AS semana,
    COALESCE(
        (SELECT CASE WHEN meta_15_pontos_atingida IS NULL THEN 'Sem dados de teste' WHEN meta_15_pontos_atingida THEN 'ATINGIDA (' || ganho_pontos_rag_vs_llm || ' pts)' ELSE 'NÃO ATINGIDA' END FROM vw_benchmark_rag_vs_llm_puro),
        'Sem dados de teste'
    )                                                                   AS status_atual

UNION ALL
SELECT
    2,
    'Fidelidade às fontes',
    '>= 90% das afirmações sustentadas',
    'Semana 2',
    COALESCE(
        (SELECT ROUND(AVG(fidelidade_pct), 1) || '%' || CASE WHEN AVG(fidelidade_pct) >= 90.0 THEN ' (OK)' ELSE ' (ABAIXO)' END FROM metricas_requisicao WHERE fidelidade_pct IS NOT NULL),
        'Sem dados'
    )

UNION ALL
SELECT
    3,
    'Recall da recuperação (top 3)',
    '>= 80% trecho certo nos 3 primeiros',
    'Semana 2',
    COALESCE(
        (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE recall_top3 IS TRUE) / NULLIF(COUNT(*), 0), 1) || '%' FROM metricas_requisicao WHERE recall_top3 IS NOT NULL),
        'Sem dados'
    )

UNION ALL
SELECT
    4,
    'Recusa correta',
    '>= 90% sem evidência para fora do escopo',
    'Semana 2',
    COALESCE(
        (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE recusa_correta IS TRUE) / NULLIF(COUNT(*), 0), 1) || '%' FROM metricas_requisicao WHERE recusa_correta IS NOT NULL),
        'Sem dados'
    )

UNION ALL
SELECT
    5,
    'Ganho verificador LLM (C vs B)',
    'Fica se ganhar >= 5 pts com <= 3 s a mais',
    'Semana 3',
    COALESCE(
        (SELECT decisao_arquitetural_final FROM vw_decisao_verificador_c_vs_b),
        'Aguardando benchmark'
    )

UNION ALL
SELECT
    6,
    'Acerto da extração OCR',
    '>= 85% dos campos lidos corretamente',
    'Semana 4',
    COALESCE(
        (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE acerto IS TRUE) / NULLIF(COUNT(*), 0), 1) || '%' FROM metricas_requisicao WHERE tipo_operacao = 'extracao_ocr' AND acerto IS NOT NULL),
        'Aguardando semana 4'
    )

UNION ALL
SELECT
    7,
    'Custo da extração',
    'Comparativo Tesseract, PaddleOCR, Gemini',
    'Semana 4',
    'Consultar view vw_benchmark_extracao_ocr'

UNION ALL
SELECT
    8,
    'Tempo de resposta (mediana no 4G)',
    'Mediana <= 10 s (10.000 ms)',
    'Semana 5',
    COALESCE(
        (SELECT ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY latencia_ms)::numeric / 1000.0, 2) || ' s' FROM metricas_requisicao WHERE latencia_ms IS NOT NULL),
        'Sem dados'
    )

UNION ALL
SELECT
    9,
    'Chamadas ao LLM',
    'Média <= 2 chamadas por resposta',
    'Semana 5',
    COALESCE(
        (SELECT ROUND(AVG(chamadas_llm), 2)::varchar FROM metricas_requisicao),
        'Sem dados'
    )

UNION ALL
SELECT
    10,
    'Avaliação de usuários',
    'Nota média >= 4 de 5 (5 a 10 pessoas)',
    'Semana 6',
    COALESCE(
        (SELECT nota_media_geral || '/5' || CASE WHEN meta_nota_4_atingida THEN ' (OK)' ELSE ' (ABAIXO)' END FROM vw_avaliacao_usuarios),
        'Aguardando semana 6'
    )
ORDER BY id_metrica;

COMMENT ON VIEW vw_painel_consolidado_10_metricas IS 'Painel consolidador do status das 10 métricas de validação aprovadas na Seção 9 do CLAUDE.md.';
