-- ============================================================
-- BanVic Analytics — Schema de staging (stg_banvic)
-- ============================================================
-- Arquitetura: dados crus do banco entram aqui após ETL, antes de
-- consumo pelo Power BI. Mantém integridade referencial e tipagem
-- correta — substitui a abordagem original de plugar Power BI direto
-- em CSV (que mascarava problemas de qualidade).

CREATE SCHEMA IF NOT EXISTS stg_banvic;

-- ------------------------------------------------------------
-- Agências
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg_banvic.agencias (
    cod_agencia        INTEGER PRIMARY KEY,
    nome               VARCHAR(120) NOT NULL,
    endereco           VARCHAR(200),
    cidade             VARCHAR(80),
    uf                 CHAR(2),
    data_abertura      DATE,
    tipo_agencia       VARCHAR(40)
);

-- ------------------------------------------------------------
-- Clientes (Pessoa Física)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg_banvic.clientes (
    cod_cliente        INTEGER PRIMARY KEY,
    primeiro_nome      VARCHAR(60),
    ultimo_nome        VARCHAR(80),
    email              VARCHAR(120),
    tipo_cliente       VARCHAR(15) NOT NULL,   -- PF / PJ
    data_nascimento    DATE,
    cpfcnpj            VARCHAR(20),
    endereco           VARCHAR(200),
    cep                VARCHAR(15),
    data_inclusao      TIMESTAMP
);

-- ------------------------------------------------------------
-- Colaboradores
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg_banvic.colaboradores (
    cod_colaborador    INTEGER PRIMARY KEY,
    primeiro_nome      VARCHAR(60),
    ultimo_nome        VARCHAR(80),
    cargo              VARCHAR(80),
    cod_agencia        INTEGER REFERENCES stg_banvic.agencias(cod_agencia),
    data_admissao      DATE
);

-- ------------------------------------------------------------
-- Contas
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg_banvic.contas (
    num_conta          VARCHAR(20) PRIMARY KEY,
    cod_cliente        INTEGER REFERENCES stg_banvic.clientes(cod_cliente),
    cod_agencia        INTEGER REFERENCES stg_banvic.agencias(cod_agencia),
    tipo_conta         VARCHAR(40),       -- Corrente / Poupanca / Salario
    data_abertura      DATE,
    saldo_total        NUMERIC(14,2),
    saldo_disponivel   NUMERIC(14,2)
);

-- ------------------------------------------------------------
-- Propostas de crédito
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg_banvic.propostas_credito (
    cod_proposta        INTEGER PRIMARY KEY,
    cod_cliente         INTEGER REFERENCES stg_banvic.clientes(cod_cliente),
    cod_colaborador     INTEGER REFERENCES stg_banvic.colaboradores(cod_colaborador),
    data_entrada        DATE NOT NULL,
    taxa_juros_mensal   NUMERIC(6,4),     -- ex: 0.0167 = 1,67% a.m.
    valor_proposta      NUMERIC(14,2),
    valor_financiamento NUMERIC(14,2),
    valor_entrada       NUMERIC(14,2),
    valor_prestacao     NUMERIC(14,2),
    qtd_parcelas        INTEGER,
    carencia            INTEGER,
    status_proposta     VARCHAR(40)        -- Aprovado / Negado / Em analise / Pendente
);

-- ------------------------------------------------------------
-- Transações
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg_banvic.transacoes (
    cod_transacao      BIGINT PRIMARY KEY,
    num_conta          VARCHAR(20) REFERENCES stg_banvic.contas(num_conta),
    data_transacao     TIMESTAMP NOT NULL,
    nome_transacao     VARCHAR(80),       -- Saque, Compra Credito, Boleto Pago, etc.
    valor_transacao    NUMERIC(14,2)
);

-- ------------------------------------------------------------
-- IPCA (dado externo — Sidra/IBGE) integrado para análise comparativa
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg_banvic.ipca_mensal (
    mes_referencia     DATE PRIMARY KEY,
    variacao_mensal    NUMERIC(6,4),      -- % de variação do mês
    acumulado_12m      NUMERIC(6,4)       -- % acumulado em 12 meses
);

-- ============================================================
-- ÍNDICES para performance das queries analíticas
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_transacoes_data ON stg_banvic.transacoes (data_transacao);
CREATE INDEX IF NOT EXISTS idx_transacoes_conta ON stg_banvic.transacoes (num_conta);
CREATE INDEX IF NOT EXISTS idx_propostas_data ON stg_banvic.propostas_credito (data_entrada);
CREATE INDEX IF NOT EXISTS idx_clientes_tipo ON stg_banvic.clientes (tipo_cliente);
CREATE INDEX IF NOT EXISTS idx_ipca_mes ON stg_banvic.ipca_mensal (mes_referencia);
