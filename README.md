# BanVic Analytics — Engenharia de Dados Completa

Versão **revisada** do Desafio Lighthouse 2024 do BanVic. A primeira entrega plugava o Power BI direto nos CSVs — funcionava, mas mascarava problemas de qualidade e não tinha como crescer. Aqui refiz com **pipeline ETL em PostgreSQL** (schema `stg_banvic`), camada de staging adequada antes do consumo do BI, e integração com **dado externo de IPCA** (IBGE/Sidra) pra dar contexto macroeconômico às análises.

---

## Por que esse refactor

| Versão original | Versão revisada (este repo) |
|---|---|
| Power BI lê CSV diretamente | Power BI lê PostgreSQL schema `stg_banvic` |
| Tipos inferidos pelo BI (erros silenciosos) | Tipos definidos no `CREATE TABLE` |
| Sem chaves estrangeiras | PK + FK garantem integridade |
| Sem dado externo | IPCA mensal integrado |
| Sem reprodutibilidade | Todo ETL versionado em `.sql` |

---

## Dataset

- **Fonte:** Desafio Indicium Lighthouse (BanVic Bank)
- **Volume:**
  - 998 clientes (PF)
  - 2.000 propostas de crédito
  - 71.999 transações (2010-2023)
  - R$ 58,1 mi movimentados
- **Dado externo:** IPCA mensal IBGE/Sidra (2020-2022)

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Banco | PostgreSQL 14+ |
| ETL | SQL puro (psql `\copy`) |
| BI | Power BI Desktop conectado via ODBC |
| Dado externo | API Sidra/IBGE → CSV → tabela `ipca_mensal` |

---

## Como rodar

```bash
git clone https://github.com/Jair-pc/banvic-analytics.git
cd banvic-analytics

# 1. Criar banco e schema
createdb banvic
psql banvic -f 01_schema_stg_banvic.sql

# 2. Colocar os CSVs em /tmp/banvic/ e rodar a carga
psql banvic -f 02_etl_carga_inicial.sql

# 3. Rodar as 4 análises (em ordem ou independentes)
psql banvic -f 03_analise_clientes.sql
psql banvic -f 04_analise_credito.sql
psql banvic -f 05_analise_ipca.sql
psql banvic -f 06_analise_transacoes.sql
```

---

## Achados principais

### 1. Clientes (998 PF)
- **Idade média:** 51,8 anos
- **100% pessoa física** — sem PJ na carteira
- Distribuição de saldo desigual (curva de Pareto típica)

### 2. Crédito (2.000 propostas)
- **Taxa média:** 1,67% a.m. (~22% a.a.)
- **Prazo médio:** 61 parcelas (5 anos)
- Distribuição por status revela funil: aprovado / pendente / negado

### 3. IPCA × Comportamento
- **IPCA acumulado 2020-2022:** 19,11%
- **Pico mensal:** 1,62% em mar/2022
- Correlação testada entre IPCA mensal e volume de saques (consultar `05_analise_ipca.sql` — função `corr()`)

### 4. Transações (71.999 / 2010-2023)
- **Volume:** R$ 58,1 mi
- **Ticket médio:** R$ 807,52
- **Tipo mais frequente:** Compra Crédito (34,7%)
- Variação YoY calculada com `LAG()` window function

---

## Estrutura do repo

```
.
├── 01_schema_stg_banvic.sql    # CREATE TABLE com PK/FK
├── 02_etl_carga_inicial.sql    # \copy dos CSVs + validação
├── 03_analise_clientes.sql     # perfil, faixa etária, saldo
├── 04_analise_credito.sql      # taxas, prazo, status
├── 05_analise_ipca.sql         # IPCA × saques × crédito + corr()
├── 06_analise_transacoes.sql   # KPIs, sazonalidade, YoY
└── README.md                   # este arquivo
```

---

## O que esse projeto demonstra

- **Modelagem relacional** com PK/FK em PostgreSQL
- **ETL via SQL** (`\copy`, validação pós-carga)
- **CTEs encadeadas** + window functions (`LAG`, `SUM OVER`)
- **Filtros condicionais** (`FILTER (WHERE ...)`) — mais limpo que `CASE` aninhado
- **Função estatística** nativa do PostgreSQL (`corr()`) para correlação
- Integração de **dado externo** (IPCA) com dado interno
- **Decisão arquitetural:** staging antes do BI, em vez de BI direto no CSV

---

## Autor

**Jair Pereira da Silva Júnior** — Analista de Dados
GitHub: [@Jair-pc](https://github.com/Jair-pc) · [Portfólio](https://github.com/Jair-pc/portfolio_site)
