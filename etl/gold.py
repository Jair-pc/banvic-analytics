"""
Camada Gold: facts e dims agregadas para consumo do Dashboard.

Responsabilidades:
- Le os parquets de data/silver/
- Cria os fact tables compactos:
    * fact_tx_evolucao   (ano,mes,agencia,faixa)        -> qtd, volume
    * fact_tx_tipo       (ano,agencia,faixa,tipo)       -> qtd, volume
    * fact_clientes      (agencia,faixa,estado,ano_inc) -> qtd, saldo
    * fact_propostas     (ano,agencia,faixa,status)     -> 6 agregados
    * fact_saques        (ano,mes,agencia,faixa)        -> volume
- Calcula os dims (agencias, faixas, estados, tipos, totais)
- Serializa o JSON compacto consumido pelo Dashboard Web V2
- Persiste cada fact/dim em data/gold/*.parquet para auditoria

Em SQL puro isso seria a camada "presentation" — fact tables + dim tables sob
um star schema. Aqui mantemos o mesmo conceito, so que em parquet + JSON.
"""
import json, os
import pandas as pd
from scipy import stats

from etl.config import SILVER_DIR, GOLD_DIR, OUTPUT_JSON, FAIXAS_ETARIAS, ESTADOS_ATIVOS
from etl.logger import get_logger

log = get_logger("gold")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _read_silver(table: str) -> pd.DataFrame:
    p = SILVER_DIR / f"{table}.parquet"
    if not p.exists():
        raise FileNotFoundError(f"silver missing: {p}")
    return pd.read_parquet(p)


def _save_gold(df: pd.DataFrame, table: str) -> None:
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    out = GOLD_DIR / f"{table}.parquet"
    df.to_parquet(out, index=False)
    log.info(f"[{table}] {len(df):,} linhas -> {out.name}")


def _faixa_to_idx(f: str) -> int:
    try:
        return FAIXAS_ETARIAS.index(f)
    except ValueError:
        return 3  # Indefinida


# ---------------------------------------------------------------------------
# pipeline gold
# ---------------------------------------------------------------------------
def build() -> dict:
    log.info("=" * 60)
    log.info("GOLD LAYER · agregacoes para o Dashboard")
    log.info("=" * 60)

    ag   = _read_silver("agencias").sort_values("cod_agencia").reset_index(drop=True)
    cli  = _read_silver("clientes")
    ct   = _read_silver("contas")
    tx   = _read_silver("transacoes")
    prop = _read_silver("propostas_credito")
    col  = _read_silver("colaboradores")
    ca   = _read_silver("colaborador_agencia")
    ipca = _read_silver("ipca")

    # --- indexes/dims ---
    AGS = ag[["cod_agencia", "nome_short", "uf", "tipo_agencia"]].to_dict("records")
    AGIDX = {r["cod_agencia"]: i for i, r in enumerate(AGS)}
    colab_por_agencia = ca.groupby("cod_agencia").size()
    EIDX = {e: i for i, e in enumerate(ESTADOS_ATIVOS)}
    TIPOS = list(tx["nome_transacao"].value_counts().index)
    TIDX = {t: i for i, t in enumerate(TIPOS)}

    cli["fidx"] = cli["faixa_etaria"].apply(_faixa_to_idx)
    cli["incY"] = cli["data_inclusao"].dt.year

    # estado do cliente = uf da agencia da conta principal
    cc = (ct[["cod_cliente", "cod_agencia", "saldo_total"]]
          .merge(ag[["cod_agencia", "uf"]], on="cod_agencia", how="left"))
    cli = cli.merge(cc.drop_duplicates("cod_cliente")
                       [["cod_cliente", "cod_agencia", "uf", "saldo_total"]],
                    on="cod_cliente", how="left")

    # join transacoes -> conta -> cliente (para fidx)
    txj = (tx.merge(ct[["num_conta", "cod_agencia", "cod_cliente"]], on="num_conta", how="left")
              .merge(cli[["cod_cliente", "fidx"]], on="cod_cliente", how="left"))
    txj["fidx"] = txj["fidx"].fillna(3).astype(int)
    txj["ai"]   = txj["cod_agencia"].map(AGIDX)
    txj["ti"]   = txj["nome_transacao"].map(TIDX)
    txj["av"]   = txj["valor_transacao"].abs()

    # --- FACT 1: evolucao mensal ---
    f1 = (txj[txj["ano"] > 0]
          .groupby(["ano", "mes", "ai", "fidx"], dropna=False)
          .agg(cnt=("av", "size"), vol=("av", "sum"))
          .reset_index())
    _save_gold(f1, "fact_tx_evolucao")

    # --- FACT 2: por tipo ---
    f2 = (txj[txj["ano"] > 0]
          .groupby(["ano", "ai", "fidx", "ti"])
          .agg(cnt=("av", "size"), vol=("av", "sum"))
          .reset_index())
    _save_gold(f2, "fact_tx_tipo")

    # --- FACT 3: clientes ---
    cli["ai"] = cli["cod_agencia"].map(AGIDX)
    cli["ei"] = cli["uf"].map(EIDX)
    f3 = (cli.dropna(subset=["ai"])
              .groupby(["ai", "fidx", "ei", "incY"])
              .agg(cnt=("cod_cliente", "size"), saldo=("saldo_total", "sum"))
              .reset_index())
    _save_gold(f3, "fact_clientes")

    # --- FACT 4: propostas ---
    prop = prop.merge(cli[["cod_cliente", "fidx", "ai"]], on="cod_cliente", how="left")
    colag = ca.set_index("cod_colaborador")["cod_agencia"].to_dict()
    prop["ai_col"] = prop["cod_colaborador"].map(lambda c: AGIDX.get(colag.get(c)))
    prop["ai"]   = prop["ai"].fillna(prop["ai_col"])
    prop["fidx"] = prop["fidx"].fillna(3).astype(int)

    def status_idx(s):
        s = str(s).lower()
        if "aprov" in s: return 1
        if "valid" in s: return 2
        if "an" in s and "lise" in s.replace("á", "a"): return 3
        return 0

    prop["si"] = prop["status_proposta"].apply(status_idx)
    prop = prop.dropna(subset=["ai"])
    f4 = (prop.groupby(["ano", "ai", "fidx", "si"])
              .agg(cnt=("cod_proposta", "size"),
                   val=("valor_proposta", "sum"),
                   jur=("taxa_juros_mensal", "sum"),
                   parc=("quantidade_parcelas", "sum"),
                   fin=("valor_financiamento", "sum"),
                   ent=("valor_entrada", "sum"))
              .reset_index())
    _save_gold(f4, "fact_propostas")

    # raw leve de propostas (para histograma de juros no front)
    prop["jur_pct"] = prop["taxa_juros_mensal"] * 100
    jbins = [0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.5]
    JL    = ["0,8-1,0", "1,0-1,2", "1,2-1,4", "1,4-1,6", "1,6-1,8",
             "1,8-2,0", "2,0-2,2", "2,2-2,5"]
    prop["jb"]  = pd.cut(prop["jur_pct"], bins=jbins, labels=JL, include_lowest=True)
    prop["jbi"] = prop["jb"].map({l: i for i, l in enumerate(JL)})

    # --- FACT 5: saques ---
    sq = txj[txj["nome_transacao"].str.lower().str.contains("saque", na=False)]
    fsq = (sq[sq["ano"] > 0]
           .groupby(["ano", "mes", "ai", "fidx"])
           .agg(vol=("av", "sum"))
           .reset_index())
    _save_gold(fsq, "fact_saques")

    # --- IPCA serie ---
    ipca["m12"] = pd.to_numeric(ipca["12_meses"], errors="coerce")
    ipS = ipca[ipca["ano"].between(2018, 2022)].sort_values(["ano", "mn"])

    # --- analise temporal (dim_dates implicito) ---
    txd = txj.dropna(subset=["data_transacao"]).copy()
    txd["date"] = txd["data_transacao"].dt.normalize()
    dly = txd.groupby("date").agg(cnt=("av", "size"), vol=("av", "sum")).reset_index()
    DUMP_THR = 200
    dump_days = dly[dly["cnt"] > DUMP_THR]
    clean = dly[dly["cnt"] <= DUMP_THR].copy()
    clean["ano"]  = clean["date"].dt.year
    clean["tri"]  = clean["date"].dt.quarter
    clean["mes"]  = clean["date"].dt.month
    clean["dow"]  = clean["date"].dt.dayofweek
    RMES = {1, 2, 3, 4, 9, 10, 11, 12}
    clean["temR"] = clean["mes"].isin(RMES)
    clean["par"]  = clean["mes"] % 2 == 0

    def tblock(df):
        tri = [{"q": int(q),
                "c": round(float(g["cnt"].mean()), 2),
                "v": int(round(g["vol"].mean()))} for q, g in df.groupby("tri")]
        wd  = [{"d": int(d),
                "c": round(float(g["cnt"].mean()), 2),
                "v": int(round(g["vol"].mean()))} for d, g in df.groupby("dow")]
        cR, sR = df[df.temR]["cnt"], df[~df.temR]["cnt"]
        pr = float(stats.ttest_ind(cR, sR, equal_var=False).pvalue) if len(cR) > 1 and len(sR) > 1 else 1.0
        pa, im = df[df.par]["vol"], df[~df.par]["vol"]
        pp = float(stats.ttest_ind(pa, im, equal_var=False).pvalue) if len(pa) > 1 and len(im) > 1 else 1.0
        return dict(
            tri=tri, wd=wd,
            rmonths=dict(comR=round(float(cR.mean()), 2),
                         semR=round(float(sR.mean()), 2),
                         p=round(pr, 4)),
            parimpar=dict(par=int(round(pa.mean())),
                          impar=int(round(im.mean())),
                          p=round(pp, 4)),
        )

    tempoByYear = {"all": tblock(clean)}
    for y in (2020, 2021, 2022):
        sub = clean[clean["ano"] == y]
        tempoByYear[str(y)] = tblock(sub) if len(sub) > 3 else None

    # --- monta JSON do Dashboard ---
    dims = dict(
        agencias=[
            {"i": i, "nome": r["nome_short"], "uf": r["uf"],
             "tipo": r["tipo_agencia"],
             "colab": int(colab_por_agencia.get(r["cod_agencia"], 0))}
            for i, r in enumerate(AGS)
        ],
        faixas=FAIXAS_ETARIAS,
        estados=ESTADOS_ATIVOS,
        tipos=TIPOS,
        jurosBins=JL,
        totals=dict(
            clientes=int(len(cli)),
            contas=int(len(ct)),
            colaboradores=int(len(col)),
            agencias=int(len(ag)),
            saldoTotal=int(round(ct["saldo_total"].sum())),
        ),
    )

    txEvo    = [[int(r.ano), int(r.mes), int(r.ai), int(r.fidx), int(r.cnt), int(round(r.vol))] for r in f1.itertuples()]
    txType   = [[int(r.ano), int(r.ai), int(r.fidx), int(r.ti), int(r.cnt), int(round(r.vol))] for r in f2.itertuples()]
    cliFact  = [[int(r.ai), int(r.fidx), int(r.ei),
                 int(r.incY) if not pd.isna(r.incY) else 0,
                 int(r.cnt),
                 int(round(r.saldo)) if not pd.isna(r.saldo) else 0] for r in f3.itertuples()]
    propFact = [[int(r.ano), int(r.ai), int(r.fidx), int(r.si),
                 int(r.cnt), int(round(r.val)),
                 round(float(r.jur), 4), int(round(r.parc)),
                 int(round(r.fin)), int(round(r.ent))] for r in f4.itertuples()]
    propRaw  = [[int(r.ano), int(r.ai), int(r.fidx),
                 int(r.jbi) if not pd.isna(r.jbi) else 0,
                 int(r.quantidade_parcelas)] for r in prop.itertuples()]
    ipcaSer  = [[int(r.ano), int(r.mn),
                 round(float(r.no_mes), 2),
                 round(float(r.m12), 2) if not pd.isna(r.m12) else None] for r in ipS.itertuples()]
    saqueFact = [[int(r.ano), int(r.mes), int(r.ai), int(r.fidx), int(round(r.vol))] for r in fsq.itertuples()]

    tempo = dict(
        byYear=tempoByYear,
        dumpDays=int(len(dump_days)),
        txClean=int(clean["cnt"].sum()),
        txTotal=int(dly["cnt"].sum()),
        dumpList=[str(d.date()) for d in dump_days["date"]],
    )

    payload = dict(
        dims=dims, txEvo=txEvo, txType=txType, cliFact=cliFact,
        propFact=propFact, propRaw=propRaw, ipcaSer=ipcaSer,
        saqueFact=saqueFact, tempo=tempo,
    )

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(OUTPUT_JSON) / 1024
    log.info(f"JSON gravado: {OUTPUT_JSON.name} ({size_kb:.0f} KB)")
    log.info(f"GOLD DONE · saldoTotal R$ {dims['totals']['saldoTotal']:,} · "
             f"agencias={len(dims['agencias'])} · txEvo={len(txEvo)} · cliFact={len(cliFact)}")

    return dict(
        json_kb=round(size_kb, 1),
        saldoTotal=dims["totals"]["saldoTotal"],
        clientes=dims["totals"]["clientes"],
        rows=dict(txEvo=len(txEvo), txType=len(txType),
                  cliFact=len(cliFact), propFact=len(propFact)),
    )


def run() -> dict:
    return build()


if __name__ == "__main__":
    run()
