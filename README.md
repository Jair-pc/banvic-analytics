# BanVic Analytics — Pipeline ETL Real

Versão **revisada** do Desafio Lighthouse 2024 do BanVic. A primeira entrega (V1) plugava o Power BI direto nos CSVs — funcionava, mas mascarava problemas de qualidade. Esta V2 implementa um **pipeline ETL real** com 2 caminhos de consumo:

1. **SQL** sobre PostgreSQL (`stg_banvic`) — para análises ad-hoc e Power BI clássico
2. **Python (Pandas)** — produz o JSON consumido pelo **[Dashboard Web V2](https://jair-pc.github.io/portfolio_site/projeto-banvic-v2-dashboard.html)** (5 páginas, KPIs em tempo de execução, sem refresh manual)

> Os dados que aparecem no Dashboard saem **diretamente deste repo** — clone, rode o ETL, e o JSON regenerado alimenta a interface.

---

## Estrutura do repo

```
banvic-analytics/
├── data/
│   └── raw/                    # 8 CSVs brutos do Desafio Lighthouse + IPCA externo
│       ├── agencias.csv
│       ├── clientes.csv
│       ├── colaboradores.csv
│       ├── colaborador_agencia.csv
│       ├── contas.csv
│       ├── propostas_credito.csv
│       ├── transacoes.csv      # 4,1 MB · ~72k transações
│       └── ipca.csv            # dado externo (IBGE/Sidra)
├── sql/
│   ├── 01_schema_stg_banvic.sql    # CREATE TABLE com PK/FK
│   ├── 02_etl_carga_inicial.sql    # \copy dos CSVs + validação
│   ├── 03_analise_clientes.sql     # perfil, faixa etária, saldo
│   ├── 04_analise_credito.sql      # taxas, prazo, status
│   ├── 05_analise_ipca.sql         # IPCA × saques × crédito (corr())
│   └── 06_analise_transacoes.sql   # KPIs, sazonalidade, YoY (LAG)
├── python/
│   ├── build_dashboard_data.py     # ETL Python → JSON do Dashboard
│   └── requirements.txt
├── output/
│   └── banvic_v2_report.json       # ~180 KB · alimenta o Dashboard Web V2
└── README.md
```

---

## Pipeline (visão arquitetural)

```
            ┌──────────────────┐
            │  data/raw/*.csv  │  ← Desafio Lighthouse 2024 + IPCA IBGE
            └────────┬─────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
┌───────────────┐         ┌────────────────────┐
│   sql/        │         │   python/          │
│   PostgreSQL  │         │   Pandas ETL       │
│   stg_banvic  │         │   build_dashboard… │
│   (Power BI)  │         │                    │
└──────┬────────┘         └─────────┬──────────┘
       │                            │
       ▼                            ▼
┌──────────────┐         ┌──────────────────────┐
│   Power BI   │         │ output/              │
│   (.pbix)    │         │ banvic_v2_report.json│
└──────────────┘         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │  Dashboard Web V2    │
                         │  (HTML + Chart.js)   │
                         └──────────────────────┘
```

---

## Caminho 1 — SQL via PostgreSQL

Boa para quem vai consumir via Power BI, Metabase ou queries ad-hoc.

```bash
# Subir um PostgreSQL local (Docker exemplo):
docker run --name banvic-pg -e POSTGRES_PASSWORD=secret -p 5432:5432 -d postgres:16

# Criar banco e schema
createdb banvic
psql banvic -f sql/01_schema_stg_banvic.sql

# Copiar CSVs pra um path acessível pelo psql e carregar
psql banvic -f sql/02_etl_carga_inicial.sql

# Rodar as 4 análises temáticas
psql banvic -f sql/03_analise_clientes.sql
psql banvic -f sql/04_analise_credito.sql
psql banvic -f sql/05_analise_ipca.sql
psql banvic -f sql/06_analise_transacoes.sql
```

### O que os scripts SQL demonstram
- **Modelagem relacional** com PK/FK (`REFERENCES`)
- **`COUNT(*) FILTER (WHERE …)`** em vez de `CASE` aninhado
- **CTEs encadeadas** + **window functions** (`LAG()` para YoY, `SUM() OVER` para acumulado)
- **`corr()` nativa** do PostgreSQL para correlação IPCA × volume de saques
- **`\copy` do psql** para carga rápida sem permissão de servidor

---

## Caminho 2 — Python ETL → JSON do Dashboard

```bash
# Instalar dependencias
pip install -r python/requirements.txt

# Rodar o ETL (le data/raw/, escreve output/banvic_v2_report.json)
python python/build_dashboard_data.py
```

Saída esperada:
```
OK  saida=output/banvic_v2_report.json  (182 KB)
txEvo rows: 2328  txType: 2139  cliFact: 206  propFact: 787  propRaw: 2000
tipos: ['Compra Crédito', 'Compra Débito', 'Pix - Realizado', …]
saldoTotal R$: 26516864
agencias: ['Matriz', 'Tatuapé', 'Campinas', 'Osasco', 'Porto Alegre', …]
```

### Estrutura do JSON
| Chave | Descrição |
|---|---|
| `dims` | Agências, faixas etárias, estados, tipos de transação, faixas de juros, **totais consolidados** (clientes, contas, colaboradores, saldo total) |
| `txEvo` | Fact compacta de transações por (ano, mês, agência, faixa etária) → contagem + volume |
| `txType` | Fact por (ano, agência, faixa, tipo de transação) |
| `cliFact` | Fact de clientes por (agência, faixa, estado, ano de inclusão) |
| `propFact` | Fact de propostas de crédito por (ano, agência, faixa, status) |
| `propRaw` | Propostas raw para o scatter taxa × valor |
| `ipcaSer` | Série mensal do IPCA |
| `saqueFact` | Fact de saques por mês para análise de correlação |
| `tempo` | Estatísticas para a página de padrões temporais (incl. exclusão dos dias de dump artificial em dez/22) |

### Decisões de modelagem
- **`dim_date` construída em runtime:** trimestre, dia-da-semana, mês com/sem "R", par/ímpar
- **Dump artificial de fim de 2022:** identificado e **excluído** das análises de sazonalidade para não distorcer padrões reais
- **Faixa etária do cliente** propagada para cada transação via JOIN `transacoes → contas → clientes`
- **Estado** do cliente derivado da agência da conta (CSV `clientes.csv` não tem UF própria)

---

## Achados principais

### Clientes (998 PF)
- **Idade média:** 51,8 anos
- **100% pessoa física** — sem PJ na carteira
- Concentração em SP (Matriz + Tatuapé + Campinas + Osasco)

### Crédito (2.000 propostas)
- **Taxa média:** 1,67% a.m. (~22% a.a.)
- **Prazo médio:** 61 parcelas (5 anos)

### IPCA × Comportamento
- **IPCA acumulado 2020-2022:** 19,11%
- **Pico mensal:** 1,62% em mar/2022
- Correlação testada entre IPCA mensal e volume de saques

### Transações (72k / 2010-2023)
- **Saldo total em carteira:** R$ 26.516.864
- **Tipo mais frequente:** Compra Crédito
- Variação YoY calculada com `LAG()` window function
- **Dump artificial em dez/22** identificado e excluído nas análises temporais

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Raw / armazenamento | CSV (Desafio Lighthouse) |
| ETL SQL | PostgreSQL 14+ · psql `\copy` |
| ETL Python | Python 3.11+ · Pandas · NumPy |
| Consumo BI | Power BI Desktop (via stg_banvic) |
| Consumo Web | Dashboard HTML + Chart.js (via JSON) |

---

## Por que dois caminhos?

| | Caminho SQL | Caminho Python |
|---|---|---|
| **Audiência** | BI Analyst / Power BI | Recrutador no portfólio web |
| **Output** | Tabelas tipadas | JSON pronto pra renderizar |
| **Refresh** | Manual (Power BI) | A cada deploy do site |
| **Vantagem** | Governança, queries ad-hoc | Zero infra — abre no navegador |

Os dois consomem a mesma `data/raw/` e produzem **as mesmas métricas** — mudou apenas a forma de entrega.

---

## Autor

**Jair Pereira da Silva Júnior** — Analista de Dados
GitHub: [@Jair-pc](https://github.com/Jair-pc) · [Portfólio](https://github.com/Jair-pc/portfolio_site)
