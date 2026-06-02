-- ============================================================
-- BanVic — Propostas, Taxas e Risco
-- ============================================================
-- 2000 propostas · taxa média 1,67% a.m. · prazo médio 61 parcelas.

-- 1. Métricas gerais
SELECT
    COUNT(*)                                          AS total_propostas,
    ROUND(AVG(taxa_juros_mensal * 100)::numeric, 2)   AS taxa_juros_media_pct,
    ROUND(AVG(qtd_parcelas)::numeric, 0)              AS prazo_medio_parcelas,
    ROUND(AVG(valor_financiamento)::numeric, 2)       AS valor_financiamento_medio
FROM stg_banvic.propostas_credito;

-- 2. Distribuição por status
SELECT
    status_proposta,
    COUNT(*)                                          AS qtd,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM stg_banvic.propostas_credito
GROUP BY status_proposta
ORDER BY qtd DESC;

-- 3. Taxa média por faixa de prazo
SELECT
    CASE
        WHEN qtd_parcelas <= 12   THEN 'curto (até 12)'
        WHEN qtd_parcelas <= 36   THEN 'médio (13-36)'
        WHEN qtd_parcelas <= 60   THEN 'longo (37-60)'
        ELSE                           'muito longo (60+)'
    END                                              AS faixa_prazo,
    COUNT(*)                                         AS qtd,
    ROUND(AVG(taxa_juros_mensal * 100)::numeric, 2)  AS taxa_media_pct
FROM stg_banvic.propostas_credito
GROUP BY 1
ORDER BY 1;

-- 4. Top 10 colaboradores por volume de proposta aprovada
SELECT
    co.cod_colaborador,
    co.primeiro_nome || ' ' || co.ultimo_nome   AS colaborador,
    co.cargo,
    COUNT(*)                                    AS qtd_propostas,
    ROUND(SUM(p.valor_financiamento)::numeric, 2) AS volume_financiado
FROM stg_banvic.propostas_credito p
JOIN stg_banvic.colaboradores      co ON co.cod_colaborador = p.cod_colaborador
WHERE p.status_proposta = 'Aprovado'
GROUP BY co.cod_colaborador, colaborador, co.cargo
ORDER BY volume_financiado DESC
LIMIT 10;
