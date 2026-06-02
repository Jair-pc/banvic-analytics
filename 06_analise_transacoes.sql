-- ============================================================
-- BanVic — Movimentações e Padrões Financeiros
-- ============================================================
-- 71.999 transações 2010-2023 · R$ 58,1 mi movimentados · ticket médio R$ 807,52.

-- 1. KPIs gerais
SELECT
    COUNT(*)                                          AS total_transacoes,
    ROUND(SUM(ABS(valor_transacao))::numeric, 2)      AS volume_total,
    ROUND(AVG(ABS(valor_transacao))::numeric, 2)      AS ticket_medio,
    MIN(data_transacao)                               AS primeira,
    MAX(data_transacao)                               AS ultima
FROM stg_banvic.transacoes;

-- 2. Por tipo de transação
SELECT
    nome_transacao,
    COUNT(*)                                          AS qtd,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_qtd,
    ROUND(SUM(ABS(valor_transacao))::numeric, 2)      AS volume
FROM stg_banvic.transacoes
GROUP BY nome_transacao
ORDER BY qtd DESC;

-- 3. Sazonalidade — média mensal de movimentação
SELECT
    EXTRACT(MONTH FROM data_transacao)::int           AS mes,
    COUNT(*)                                          AS qtd_transacoes,
    ROUND(AVG(ABS(valor_transacao))::numeric, 2)      AS ticket_medio,
    ROUND(SUM(ABS(valor_transacao))::numeric, 2)      AS volume_total
FROM stg_banvic.transacoes
GROUP BY mes
ORDER BY mes;

-- 4. Evolução anual + window function (variação YoY)
WITH anual AS (
    SELECT
        EXTRACT(YEAR FROM data_transacao)::int        AS ano,
        SUM(ABS(valor_transacao))                     AS volume
    FROM stg_banvic.transacoes
    GROUP BY 1
)
SELECT
    ano,
    ROUND(volume::numeric, 2)                                                  AS volume,
    ROUND(LAG(volume) OVER (ORDER BY ano)::numeric, 2)                         AS volume_ano_anterior,
    ROUND(((volume / NULLIF(LAG(volume) OVER (ORDER BY ano), 0)) - 1) * 100, 2) AS variacao_yoy_pct
FROM anual
ORDER BY ano;

-- 5. Concentração — Top 10 contas que mais movimentaram
SELECT
    num_conta,
    COUNT(*)                                          AS qtd_transacoes,
    ROUND(SUM(ABS(valor_transacao))::numeric, 2)      AS volume
FROM stg_banvic.transacoes
GROUP BY num_conta
ORDER BY volume DESC
LIMIT 10;
