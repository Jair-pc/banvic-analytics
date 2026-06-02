"""
Camada Silver: limpeza, tipagem e deduplicacao a partir do Bronze.

Responsabilidades:
- Le os parquets de data/bronze/
- Aplica tipos corretos (datas, numericos)
- Remove duplicatas pela PK
- Adiciona colunas derivadas estaveis (idade, faixa_etaria, ano, mes, dia_semana)
- Padroniza nomes (curto, sem prefixo "Agencia ", etc)
- Escreve em data/silver/<nome>.parquet

Cada funcao silver_* devolve o DataFrame ja tratado para reutilizacao em testes.
"""
import pandas as pd
from etl.config import BRONZE_DIR, SILVER_DIR, MES_PT, REFERENCE_DATE
from etl.logger import get_logger

log = get_logger("silver")

REF_TS_NAIVE = pd.Timestamp(REFERENCE_DATE)
REF_TS_UTC   = pd.Timestamp(REFERENCE_DATE, tz="UTC")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _read(table: str) -> pd.DataFrame:
    p = BRONZE_DIR / f"{table}.parquet"
    if not p.exists():
        raise FileNotFoundError(f"bronze missing: {p}")
    df = pd.read_parquet(p)
    # remove cols de metadado da bronze (nao usadas em silver)
    return df.drop(columns=[c for c in df.columns if c.startswith("_")], errors="ignore")


def _save(df: pd.DataFrame, table: str) -> None:
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    out = SILVER_DIR / f"{table}.parquet"
    df.to_parquet(out, index=False)
    log.info(f"[{table}] {len(df):,} linhas -> {out.name}")


def _faixa_etaria(idade: float) -> str:
    if pd.isna(idade):
        return "Indefinida"
    if idade < 25:
        return "Jovem (<25)"
    if idade < 60:
        return "Adulto (25-59)"
    return "Idoso (60+)"


# ---------------------------------------------------------------------------
# transformacoes por tabela
# ---------------------------------------------------------------------------
def silver_agencias() -> pd.DataFrame:
    df = _read("agencias")
    df["nome_short"] = (
        df["nome"].astype(str)
                  .str.replace("Agência ", "", regex=False)
                  .str.replace("Agencia ", "", regex=False)
                  .str.strip()
    )
    df = df.drop_duplicates(subset=["cod_agencia"]).reset_index(drop=True)
    _save(df, "agencias")
    return df


def silver_clientes() -> pd.DataFrame:
    df = _read("clientes")
    df["data_nascimento"] = pd.to_datetime(df["data_nascimento"], errors="coerce")
    df["data_inclusao"]   = pd.to_datetime(df["data_inclusao"], utc=True, errors="coerce")
    df["idade"] = ((REF_TS_NAIVE - df["data_nascimento"]).dt.days / 365.25).round(1)
    df["faixa_etaria"] = df["idade"].apply(_faixa_etaria)
    df = df.drop_duplicates(subset=["cod_cliente"]).reset_index(drop=True)
    _save(df, "clientes")
    return df


def silver_contas() -> pd.DataFrame:
    df = _read("contas")
    df["saldo_total"]      = pd.to_numeric(df["saldo_total"], errors="coerce")
    df["saldo_disponivel"] = pd.to_numeric(df.get("saldo_disponivel"), errors="coerce")
    df["data_abertura"]    = pd.to_datetime(df["data_abertura"], errors="coerce")
    df = df.drop_duplicates(subset=["num_conta"]).reset_index(drop=True)
    _save(df, "contas")
    return df


def silver_transacoes() -> pd.DataFrame:
    df = _read("transacoes")
    df["data_transacao"] = pd.to_datetime(df["data_transacao"], format="mixed",
                                          utc=True, errors="coerce")
    df = df.dropna(subset=["data_transacao"]).copy()
    df["valor_transacao"] = pd.to_numeric(df["valor_transacao"], errors="coerce")
    df["valor_abs"]       = df["valor_transacao"].abs()
    df["ano"]             = df["data_transacao"].dt.year.astype("int32")
    df["mes"]             = df["data_transacao"].dt.month.astype("int32")
    df["dia_semana"]      = df["data_transacao"].dt.dayofweek.astype("int32")
    df = df.drop_duplicates(subset=["cod_transacao"]).reset_index(drop=True)
    _save(df, "transacoes")
    return df


def silver_propostas_credito() -> pd.DataFrame:
    df = _read("propostas_credito")
    df["data_entrada_proposta"] = pd.to_datetime(df["data_entrada_proposta"],
                                                  utc=True, errors="coerce")
    for c in ["taxa_juros_mensal", "valor_proposta", "valor_financiamento",
              "valor_entrada", "valor_prestacao"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ano"] = df["data_entrada_proposta"].dt.year.fillna(0).astype("int32")
    df = df.drop_duplicates(subset=["cod_proposta"]).reset_index(drop=True)
    _save(df, "propostas_credito")
    return df


def silver_colaboradores() -> pd.DataFrame:
    df = _read("colaboradores").drop_duplicates(subset=["cod_colaborador"]).reset_index(drop=True)
    _save(df, "colaboradores")
    return df


def silver_colaborador_agencia() -> pd.DataFrame:
    df = _read("colaborador_agencia").drop_duplicates().reset_index(drop=True)
    _save(df, "colaborador_agencia")
    return df


def silver_ipca() -> pd.DataFrame:
    df = _read("ipca")
    df["mn"] = df["mes"].astype(str).str.upper().map(MES_PT)
    df = df.dropna(subset=["mn"]).reset_index(drop=True)
    _save(df, "ipca")
    return df


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------
def run() -> dict:
    log.info("=" * 60)
    log.info("SILVER LAYER · limpeza + tipagem + dedup")
    log.info("=" * 60)

    summary = {
        "agencias":            len(silver_agencias()),
        "clientes":            len(silver_clientes()),
        "contas":              len(silver_contas()),
        "transacoes":          len(silver_transacoes()),
        "propostas_credito":   len(silver_propostas_credito()),
        "colaboradores":       len(silver_colaboradores()),
        "colaborador_agencia": len(silver_colaborador_agencia()),
        "ipca":                len(silver_ipca()),
    }
    log.info(f"SILVER DONE · {summary}")
    return summary


if __name__ == "__main__":
    run()
