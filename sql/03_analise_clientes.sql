-- ============================================================
-- BanVic — Perfil e Segmentação dos Clientes
-- ============================================================
-- 998 clientes, todos PF, idade média ~51,8 anos.

-- 1. Total e tipo
SELECT
    COUNT(*)                                              AS total_clientes,
    COUNT(*) FILTER (WHERE tipo_cliente = 'PF')           AS pessoas_fisicas,
    COUNT(*) FILTER (WHERE tipo_cliente = 'PJ')           AS pessoas_juridicas,
    ROUND(AVG(EXTRACT(YEAR FROM age(data_nascimento)))::numeric, 1) AS idade_media
FROM stg_banvic.clientes;

-- 2. Distribuição por UF (top 5)
SELECT
    SPLIT_PART(endereco, '/', -1)   AS uf_aprox,
    COUNT(*)                        AS qtd_clientes
FROM stg_banvic.clientes
GROUP BY 1
ORDER BY qtd_clientes DESC
LIMIT 5;

-- 3. Distribuição por faixa etária
SELECT
    CASE
        WHEN EXTRACT(YEAR FROM age(data_nascimento)) < 30  THEN 'a) <30'
        WHEN EXTRACT(YEAR FROM age(data_nascimento)) < 45  THEN 'b) 30-44'
        WHEN EXTRACT(YEAR FROM age(data_nascimento)) < 60  THEN 'c) 45-59'
        ELSE 'd) 60+'
    END                                AS faixa,
    COUNT(*)                           AS qtd,
    ROUND(AVG(EXTRACT(YEAR FROM age(data_nascimento)))::numeric, 1) AS idade_media_faixa
FROM stg_banvic.clientes
GROUP BY 1
ORDER BY 1;

-- 4. Saldo médio por cliente (juntando contas)
SELECT
    c.cod_cliente,
    c.primeiro_nome || ' ' || c.ultimo_nome AS nome,
    SUM(ct.saldo_total)                     AS saldo_total,
    COUNT(ct.num_conta)                     AS qtd_contas
FROM stg_banvic.clientes c
JOIN stg_banvic.contas  ct ON ct.cod_cliente = c.cod_cliente
GROUP BY c.cod_cliente, nome
ORDER BY saldo_total DESC
LIMIT 10;
