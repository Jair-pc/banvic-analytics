# BanVic Analytics — Pipeline ETL em Camadas (Bronze · Silver · Gold)

Versão **revisada** do Desafio Lighthouse 2024 do BanVic, agora com um **pipeline ETL real em arquitetura medallion** rodando em Python + Pandas + Parquet. Os dados que aparecem no [Dashboard Web V2](https://github.com/Jair-pc/portfolio_site) saem **deste pipeline** — clone, rode `python -m etl.pipeline`, e o JSON é regenerado a partir dos CSVs brutos.

> Comparativo com a versão original: ver **[Jair-pc/banvic-v1-powerbi](https://github.com/Jair-pc/banvic-v1-powerbi)** (entrega original em Power BI).

---

## Arquitetura — Medallion adaptado pra Pandas

```
                    data/raw/*.csv   (8 CSVs · 4,6 MB)
                          │
                          ▼
                    ┌─────────────┐
                    │   BRONZE    │   ingestão crua + metadados
                    │  etl/bronze │   (_source_file, _ingestion_ts, _row_idx)
                    └──────┬──────┘
                           │  data/bronze/*.parquet
                           ▼
                    ┌─────────────┐
                    │   SILVER    │   limpeza, tipagem, dedup
                    │  etl/silver │   + colunas derivadas (idade, faixa, ano/mês)
                    └──────┬──────┘
                           │  data/silver/*.parquet
                           ▼
                    ┌─────────────┐
                    │    GOLD     │   5 fact tables + dims
                    │  etl/gold   │   + JSON compacto pro Dashboard
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
        data/gold/*.parquet      output/banvic_v2_report.json
        (auditoria/BI)           (Dashboard Web V2)

                ┌─────────────────────────┐
                │  etl/validate           │  ← roda após cada camada
                │  8 data quality checks  │     (PKs, datas, totais, JSON keys)
                └─────────────────────────┘
```

---

## Por que medallion (e não fazer tudo num script só)

A V1 fazia toda a transformação dentro do Power BI (Power Query). A V2 inicial fazia tudo em um único script Python. **Nenhum dos dois é ETL**. Pipeline real precisa de:

| Característica | Script único | Pipeline medallion |
|---|---|---|
| Reprocessar só a etapa que mudou | ❌ refaz tudo | ✅ `--only silver` |
| Auditoria do estado intermediário | ❌ memória | ✅ Parquet em cada camada |
| Detectar regressão (data quality) | ❌ | ✅ `etl/validate.py` |
| Falha numa etapa não corrompe a próxima | ❌ | ✅ isolamento por camada |
| Logging estruturado | ❌ print | ✅ `logs/etl_YYYYMMDD.log` |
| Plugar nova fonte | ❌ refactor | ✅ adicionar 1 entrada em `RAW_TABLES` |

---

## Estrutura do repo

```
banvic-analytics/
├── data/
│   ├── raw/                          # 8 CSVs brutos (~4,6 MB)
│   ├── bronze/                       # ingestão crua + metadados (parquet)
│   ├── silver/                       # limpa, tipada, dedup (parquet)
│   └── gold/                         # facts + dims agregados (parquet)
├── etl/
│   ├── __init__.py
│   ├── config.py                     # paths, encodings, dims
│   ├── logger.py                     # logger compartilhado (arquivo + stdout)
│   ├── bronze.py                     # raw → bronze
│   ├── silver.py                     # bronze → silver
│   ├── gold.py                       # silver → gold (+ JSON)
│   ├── validate.py                   # 8 checks de qualidade
│   └── pipeline.py                   # orquestrador
├── sql/                              # caminho alternativo PostgreSQL (Power BI)
│   ├── 01_schema_stg_banvic.sql
│   ├── 02_etl_carga_inicial.sql
│   ├── 03_analise_clientes.sql
│   ├── 04_analise_credito.sql
│   ├── 05_analise_ipca.sql
│   └── 06_analise_transacoes.sql
├── output/
│   └── banvic_v2_report.json         # ~180 KB · consumido pelo Dashboard Web
├── logs/                             # logs estruturados de cada execução
├── docs/arquitetura.webp
├── requirements.txt
└── README.md
```

---

## Como rodar

### 1. Setup
```bash
git clone https://github.com/Jair-pc/banvic-analytics.git
cd banvic-analytics
pip install -r requirements.txt
```

### 2. Pipeline completo (bronze → silver → gold → validate)
```bash
python -m etl.pipeline
```

Saída esperada:
```
2026-06-02 08:01:20 INFO [pipeline] >>> START bronze
2026-06-02 08:01:20 INFO [bronze] [agencias] 10 linhas (enc=utf-8-sig) -> agencias.parquet
2026-06-02 08:01:20 INFO [bronze] [clientes] 998 linhas (enc=utf-8-sig) -> clientes.parquet
2026-06-02 08:01:20 INFO [bronze] [transacoes] 71,999 linhas (enc=utf-8-sig) -> transacoes.parquet
...
2026-06-02 08:01:28 INFO [pipeline] >>> START gold
2026-06-02 08:01:28 INFO [gold] [fact_tx_evolucao] 2,288 linhas -> fact_tx_evolucao.parquet
2026-06-02 08:01:29 INFO [gold] JSON gravado: banvic_v2_report.json (181 KB)
2026-06-02 08:01:29 INFO [gold] GOLD DONE · saldoTotal R$ 26,516,864 · agencias=10 · txEvo=2288
2026-06-02 08:01:29 INFO [pipeline] >>> START validate
2026-06-02 08:01:29 INFO [validate] [PASS] bronze.files: bronze: 8 arquivos presentes
2026-06-02 08:01:29 INFO [validate] [PASS] silver.pks: silver: PKs distintas em todas as tabelas
2026-06-02 08:01:29 INFO [validate] [PASS] gold.totals_match: silver=71,999 ~ gold=71,999
2026-06-02 08:01:29 INFO [validate] VALIDATE DONE · passed=8/8
2026-06-02 08:01:29 INFO [pipeline] BANVIC ETL · sucesso em 9.31s
```

### 3. Re-rodar só uma camada
```bash
python -m etl.pipeline --only gold        # re-agrega sem re-ingerir
python -m etl.pipeline --only validate    # só os data quality checks
python -m etl.pipeline --skip-bronze      # bronze já está OK, refaz dali pra frente
```

---

## O que cada camada faz

### Bronze (`etl/bronze.py`)
- Lê CSVs de `data/raw/`
- **Tenta UTF-8-BOM, UTF-8, Latin-1** nessa ordem (pegadinha do dataset Lighthouse)
- **Não transforma nada** — mantém os dados como vieram
- Adiciona `_source_file`, `_ingestion_ts`, `_row_idx` a cada linha
- Escreve `data/bronze/<tabela>.parquet`

### Silver (`etl/silver.py`)
- Lê parquets de `data/bronze/`
- **Tipa colunas** (datas, numéricos)
- **Dedup** por PK em cada tabela
- **Adiciona colunas derivadas** estáveis:
  - `agencias.nome_short` ("Agência Matriz" → "Matriz")
  - `clientes.idade`, `clientes.faixa_etaria`
  - `transacoes.valor_abs`, `transacoes.ano`, `transacoes.mes`, `transacoes.dia_semana`
  - `propostas.ano`
  - `ipca.mn` (mês em número)
- Escreve `data/silver/<tabela>.parquet`

### Gold (`etl/gold.py`)
- Lê parquets de `data/silver/`
- **Cria 5 fact tables compactas:**
  - `fact_tx_evolucao(ano, mes, agencia, faixa) → qtd, volume`
  - `fact_tx_tipo(ano, agencia, faixa, tipo) → qtd, volume`
  - `fact_clientes(agencia, faixa, estado, ano_inc) → qtd, saldo`
  - `fact_propostas(ano, agencia, faixa, status) → 6 agregados`
  - `fact_saques(ano, mes, agencia, faixa) → volume`
- **Cria os dims** (agências, faixas, estados, tipos, totais)
- **Análise temporal extra**: identifica o **dump artificial de fim de 2022** (dias com `> 200` transações) e exclui das análises de padrão
- Serializa o JSON compacto consumido pelo Dashboard Web V2

### Validate (`etl/validate.py`)
8 data quality checks executados após Gold:

| Check | O que faz |
|---|---|
| `bronze.files` | Confirma que os 8 parquets bronze existem |
| `bronze.non_empty` | Nenhuma tabela bronze veio vazia |
| `silver.pks` | PKs únicas em agencias / clientes / contas / transacoes / propostas / colaboradores |
| `silver.dates` | Toda transação com `data_transacao` válida |
| `silver.saldos` | Reporta contas com saldo negativo / null (informativo) |
| `gold.facts` | 5 fact tables existem |
| `gold.totals_match` | Total de transações em `fact_tx_evolucao` bate com silver |
| `gold.json_keys` | JSON final tem as 9 chaves esperadas pelo Dashboard |

Falhas viram código de saída `2` (pra integrar com CI).

---

## Logging

Cada execução grava em `logs/etl_YYYYMMDD.log`. Formato:
```
2026-06-02 08:01:28 INFO    [gold] JSON gravado: banvic_v2_report.json (181 KB)
2026-06-02 08:01:29 INFO    [validate] [PASS] gold.totals_match: silver=71,999 ~ gold=71,999
```

Os logs ecoam no stdout também (útil em CI / `crontab`).

---

## Caminho alternativo — SQL via PostgreSQL

Para quem prefere consumir via Power BI / Metabase clássico, os scripts em `sql/` reproduzem o mesmo trabalho em **PostgreSQL puro** (`stg_banvic` schema com PK/FK). Os números entre os dois caminhos são consistentes — clone o repo, rode os dois e compare.

```bash
createdb banvic
psql banvic -f sql/01_schema_stg_banvic.sql
psql banvic -f sql/02_etl_carga_inicial.sql
psql banvic -f sql/03_analise_clientes.sql      # ... e os outros 3
```

---

## Achados principais (consumidos pelo Dashboard)

### Clientes (998 PF)
- **Idade média:** 51,8 anos
- **100% pessoa física** — sem PJ na carteira

### Crédito (2.000 propostas)
- **Taxa média:** 1,67% a.m. (~22% a.a.)
- **Prazo médio:** 61 parcelas (5 anos)

### IPCA × Comportamento
- **IPCA acumulado 2020-2022:** 19,11%
- **Pico mensal:** 1,62% em mar/2022

### Transações (72k / 2010-2023)
- **Saldo total em carteira:** R$ 26.516.864
- **Tipo mais frequente:** Compra Crédito
- **Dump artificial em dez/22** detectado e excluído das análises temporais

---

## Stack

| Camada | Tecnologia |
|---|---|
| Storage colunar | Parquet (via PyArrow) |
| ETL | Python 3.11+ · Pandas 2 · NumPy |
| DQ checks | Funções puras + SciPy (t-test em padrões temporais) |
| Logging | `logging` stdlib (arquivo + stdout) |
| Orquestração | CLI `argparse` + `python -m etl.pipeline` |
| Consumo BI clássico | PostgreSQL + Power BI |
| Consumo Web | HTML + Chart.js (le `output/banvic_v2_report.json`) |

---

## Próximos passos possíveis

Coisas que um projeto em produção teria e que ficaram fora do escopo aqui:

- [ ] **Airflow / Prefect** como orquestrador (em vez de CLI manual)
- [ ] **Great Expectations** ou **pandera** pros checks (em vez de funções soltas)
- [ ] **Schedule diário** com cron / GitHub Actions
- [ ] **Incremental load** na silver (hoje é full refresh)
- [ ] **Particionamento por ano** nos parquets grandes (transacoes)
- [ ] **dbt** rodando sobre PostgreSQL (no caminho SQL)

Cada um desses é um upgrade incremental sobre a base atual — a arquitetura medallion abre caminho pra eles.

---

## Autor

**Jair Pereira da Silva Júnior** — Analista de Dados
GitHub: [@Jair-pc](https://github.com/Jair-pc) · [Portfólio](https://github.com/Jair-pc/portfolio_site)

> Desafio fictício criado pela **Lighthouse / Indicium** para o programa de Engenharia de Analytics 2024.
