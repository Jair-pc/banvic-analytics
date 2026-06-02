-- ============================================================
-- BanVic — Carga inicial dos CSVs para o schema stg_banvic
-- ============================================================
-- Premissa: arquivos CSV já foram colocados em /tmp/banvic/
-- Usar \copy do psql para evitar permissão de servidor.

-- 1. Agências
\copy stg_banvic.agencias (cod_agencia, nome, endereco, cidade, uf, data_abertura, tipo_agencia) FROM '/tmp/banvic/agencias.csv' DELIMITER ',' CSV HEADER;

-- 2. Clientes
\copy stg_banvic.clientes (cod_cliente, primeiro_nome, ultimo_nome, email, tipo_cliente, data_nascimento, cpfcnpj, endereco, cep, data_inclusao) FROM '/tmp/banvic/clientes.csv' DELIMITER ',' CSV HEADER;

-- 3. Colaboradores
\copy stg_banvic.colaboradores (cod_colaborador, primeiro_nome, ultimo_nome, cargo, cod_agencia, data_admissao) FROM '/tmp/banvic/colaboradores.csv' DELIMITER ',' CSV HEADER;

-- 4. Contas
\copy stg_banvic.contas (num_conta, cod_cliente, cod_agencia, tipo_conta, data_abertura, saldo_total, saldo_disponivel) FROM '/tmp/banvic/contas.csv' DELIMITER ',' CSV HEADER;

-- 5. Propostas de crédito
\copy stg_banvic.propostas_credito FROM '/tmp/banvic/propostas_credito.csv' DELIMITER ',' CSV HEADER;

-- 6. Transações (arquivo maior — pode demorar)
\copy stg_banvic.transacoes (cod_transacao, num_conta, data_transacao, nome_transacao, valor_transacao) FROM '/tmp/banvic/transacoes.csv' DELIMITER ',' CSV HEADER;

-- 7. IPCA externo (fonte: IBGE/Sidra)
\copy stg_banvic.ipca_mensal FROM '/tmp/banvic/ipca_mensal.csv' DELIMITER ',' CSV HEADER;

-- ============================================================
-- Validação básica pós-carga
-- ============================================================
SELECT 'agencias'           AS tabela, COUNT(*) AS linhas FROM stg_banvic.agencias
UNION ALL SELECT 'clientes',            COUNT(*) FROM stg_banvic.clientes
UNION ALL SELECT 'colaboradores',       COUNT(*) FROM stg_banvic.colaboradores
UNION ALL SELECT 'contas',              COUNT(*) FROM stg_banvic.contas
UNION ALL SELECT 'propostas_credito',   COUNT(*) FROM stg_banvic.propostas_credito
UNION ALL SELECT 'transacoes',          COUNT(*) FROM stg_banvic.transacoes
UNION ALL SELECT 'ipca_mensal',         COUNT(*) FROM stg_banvic.ipca_mensal;
