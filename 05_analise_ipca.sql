-- ============================================================
-- BanVic — IPCA × Comportamento do Cliente
-- ============================================================
-- IPCA acumulado 2020-2022: 19,11% · pico mensal MAR/2022: 1,62%.
-- Pergunta: a inflação mensal se correlaciona com volume de saques ou crédito?

-- 1. IPCA mensal e acumulado no período
WITH ipca AS (
    SELECT
        mes_referencia,
        variacao_mensal * 100                                            AS var_mensal_pct,
        SUM(variacao_mensal) OVER (ORDER BY mes_referencia) * 100        AS acumulado_pct
    FROM stg_banvic.ipca_mensal
    WHERE mes_referencia BETWEEN '2020-01-01' AND '2022-12-31'
)
SELECT * FROM ipca ORDER BY mes_referencia;

-- 2. Saques por mês × IPCA do mês
WITH saques_mes AS (
    SELECT
        date_trunc('month', data_transacao)::date                AS mes,
        SUM(ABS(valor_transacao))                                AS volume_saques,
        COUNT(*)                                                 AS qtd_saques
    FROM stg_banvic.transacoes
    WHERE nome_transacao ILIKE '%saque%'
    GROUP BY 1
)
SELECT
    s.mes,
    s.qtd_saques,
    ROUND(s.volume_saques::numeric, 2)                  AS volume_saques,
    ROUND((i.variacao_mensal * 100)::numeric, 2)        AS ipca_mes_pct
FROM saques_mes s
LEFT JOIN stg_banvic.ipca_mensal i ON i.mes_referencia = s.mes
ORDER BY s.mes;

-- 3. Crédito novo por mês × IPCA
WITH credito_mes AS (
    SELECT
        date_trunc('month', data_entrada)::date         AS mes,
        SUM(valor_financiamento)                        AS volume_credito,
        COUNT(*)                                        AS qtd_propostas
    FROM stg_banvic.propostas_credito
    WHERE status_proposta = 'Aprovado'
    GROUP BY 1
)
SELECT
    c.mes,
    c.qtd_propostas,
    ROUND(c.volume_credito::numeric, 2)                 AS volume_credito,
    ROUND((i.variacao_mensal * 100)::numeric, 2)        AS ipca_mes_pct
FROM credito_mes c
LEFT JOIN stg_banvic.ipca_mensal i ON i.mes_referencia = c.mes
ORDER BY c.mes;

-- 4. Correlação simples (Pearson) entre IPCA e volume de saques
WITH base AS (
    SELECT
        i.variacao_mensal                               AS ipca,
        SUM(ABS(t.valor_transacao))                     AS saques
    FROM stg_banvic.ipca_mensal i
    LEFT JOIN stg_banvic.transacoes t
        ON date_trunc('month', t.data_transacao)::date = i.mes_referencia
        AND t.nome_transacao ILIKE '%saque%'
    WHERE i.mes_referencia BETWEEN '2020-01-01' AND '2022-12-31'
    GROUP BY i.variacao_mensal, i.mes_referencia
)
SELECT corr(ipca, saques) AS correlacao_ipca_saques FROM base;
