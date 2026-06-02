"""
Camada Bronze: ingestao crua dos CSVs.

Responsabilidades:
- Le os CSVs de data/raw/
- Tenta os encodings na ordem definida em config.ENCODINGS
- NAO transforma os dados (mantem como vieram)
- Adiciona metadados de origem (_source_file, _ingestion_ts, _row_idx)
- Escreve cada tabela em data/bronze/<nome>.parquet
"""
from datetime import datetime, timezone
import pandas as pd

from etl.config import RAW_DIR, BRONZE_DIR, RAW_TABLES, ENCODINGS
from etl.logger import get_logger

log = get_logger("bronze")


def _read_csv_safe(path):
    """Le o CSV tentando varios encodings. Retorna (df, encoding_usado)."""
    last_err = None
    for enc in ENCODINGS:
        try:
            df = pd.read_csv(path, encoding=enc)
            return df, enc
        except UnicodeDecodeError as e:
            last_err = e
            continue
    # ultimo recurso
    df = pd.read_csv(path, encoding="latin-1", on_bad_lines="warn")
    return df, "latin-1 (fallback)"


def ingest_table(table: str, csv_name: str) -> pd.DataFrame:
    src = RAW_DIR / csv_name
    if not src.exists():
        log.error(f"raw file missing: {src}")
        raise FileNotFoundError(src)

    df, enc = _read_csv_safe(src)
    n = len(df)

    df["_source_file"]  = csv_name
    df["_ingestion_ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    df["_row_idx"]      = range(n)

    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out = BRONZE_DIR / f"{table}.parquet"
    df.to_parquet(out, index=False)

    log.info(f"[{table}] {n:,} linhas (enc={enc}) -> {out.name}")
    return df


def run() -> dict:
    """Executa a ingestao de todas as tabelas raw. Retorna {tabela: n_linhas}."""
    log.info("=" * 60)
    log.info("BRONZE LAYER · ingestao raw -> bronze")
    log.info("=" * 60)

    summary = {}
    for table, csv in RAW_TABLES.items():
        df = ingest_table(table, csv)
        summary[table] = len(df)

    total = sum(summary.values())
    log.info(f"BRONZE DONE · {len(summary)} tabelas · {total:,} linhas total")
    return summary


if __name__ == "__main__":
    run()
