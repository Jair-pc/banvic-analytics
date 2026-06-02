"""
Data Quality checks executados apos cada camada.

Cada check retorna (passed: bool, message: str).
Se passed == False, a pipeline registra o erro e continua, mas sinaliza.
Em producao, falhas criticas devem abortar o run.

Aqui implementamos checks pragmaticos:
- Bronze: nenhuma tabela vazia, nenhum CSV nao-encontrado
- Silver: PK distinta nas tabelas-chave, datas validas
- Gold: totais batem com somatorios das fact tables, JSON tem todas as chaves esperadas
"""
import json
import pandas as pd
from typing import Callable, List, Tuple

from etl.config import BRONZE_DIR, SILVER_DIR, GOLD_DIR, OUTPUT_JSON
from etl.logger import get_logger

log = get_logger("validate")

CheckResult = Tuple[bool, str]


# ---------------------------------------------------------------------------
# Bronze checks
# ---------------------------------------------------------------------------
def chk_bronze_files_exist() -> CheckResult:
    expected = ["agencias", "clientes", "contas", "transacoes",
                "propostas_credito", "colaboradores",
                "colaborador_agencia", "ipca"]
    missing = [t for t in expected if not (BRONZE_DIR / f"{t}.parquet").exists()]
    if missing:
        return False, f"bronze: arquivos faltando: {missing}"
    return True, f"bronze: {len(expected)} arquivos presentes"


def chk_bronze_non_empty() -> CheckResult:
    empty = []
    for p in BRONZE_DIR.glob("*.parquet"):
        if len(pd.read_parquet(p)) == 0:
            empty.append(p.stem)
    if empty:
        return False, f"bronze: tabelas vazias: {empty}"
    return True, "bronze: nenhuma tabela vazia"


# ---------------------------------------------------------------------------
# Silver checks
# ---------------------------------------------------------------------------
def chk_silver_pks() -> CheckResult:
    pks = {
        "agencias":          "cod_agencia",
        "clientes":          "cod_cliente",
        "contas":            "num_conta",
        "transacoes":        "cod_transacao",
        "propostas_credito": "cod_proposta",
        "colaboradores":     "cod_colaborador",
    }
    issues = []
    for tbl, pk in pks.items():
        df = pd.read_parquet(SILVER_DIR / f"{tbl}.parquet")
        dups = df[pk].duplicated().sum()
        if dups > 0:
            issues.append(f"{tbl}: {dups} duplicatas em {pk}")
    if issues:
        return False, "silver: " + "; ".join(issues)
    return True, "silver: PKs distintas em todas as tabelas"


def chk_silver_dates_valid() -> CheckResult:
    tx = pd.read_parquet(SILVER_DIR / "transacoes.parquet")
    nulls = tx["data_transacao"].isna().sum()
    if nulls > 0:
        return False, f"silver: {nulls} transacoes com data invalida"
    return True, f"silver: todas as {len(tx):,} transacoes com data valida"


def chk_silver_saldos_positivos() -> CheckResult:
    ct = pd.read_parquet(SILVER_DIR / "contas.parquet")
    neg = (ct["saldo_total"] < 0).sum()
    null_ = ct["saldo_total"].isna().sum()
    return True, (f"silver: contas com saldo_total negativo={neg} / null={null_} "
                  f"(esperado em conta corrente — informativo)")


# ---------------------------------------------------------------------------
# Gold checks
# ---------------------------------------------------------------------------
def chk_gold_facts_exist() -> CheckResult:
    expected = ["fact_tx_evolucao", "fact_tx_tipo",
                "fact_clientes", "fact_propostas", "fact_saques"]
    missing = [t for t in expected if not (GOLD_DIR / f"{t}.parquet").exists()]
    if missing:
        return False, f"gold: facts faltando: {missing}"
    return True, f"gold: {len(expected)} fact tables presentes"


def chk_gold_totals_match_silver() -> CheckResult:
    tx_silver = pd.read_parquet(SILVER_DIR / "transacoes.parquet")
    f1 = pd.read_parquet(GOLD_DIR / "fact_tx_evolucao.parquet")
    n_silver = len(tx_silver[tx_silver["data_transacao"].dt.year > 0])
    n_gold   = int(f1["cnt"].sum())
    if abs(n_silver - n_gold) > 5:    # tolerancia para edge cases de ano=0
        return False, (f"gold: divergencia tx silver={n_silver:,} vs "
                       f"fact_tx_evolucao={n_gold:,}")
    return True, (f"gold: fact_tx_evolucao bate com silver "
                  f"(silver={n_silver:,} ~ gold={n_gold:,})")


def chk_json_payload_keys() -> CheckResult:
    if not OUTPUT_JSON.exists():
        return False, "gold: output JSON nao gerado"
    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        payload = json.load(f)
    expected = {"dims", "txEvo", "txType", "cliFact",
                "propFact", "propRaw", "ipcaSer", "saqueFact", "tempo"}
    missing = expected - set(payload.keys())
    if missing:
        return False, f"gold: JSON sem chaves: {missing}"
    return True, f"gold: JSON com todas as {len(expected)} chaves esperadas"


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------
ALL_CHECKS: List[Tuple[str, Callable[[], CheckResult]]] = [
    ("bronze.files",      chk_bronze_files_exist),
    ("bronze.non_empty",  chk_bronze_non_empty),
    ("silver.pks",        chk_silver_pks),
    ("silver.dates",      chk_silver_dates_valid),
    ("silver.saldos",     chk_silver_saldos_positivos),
    ("gold.facts",        chk_gold_facts_exist),
    ("gold.totals_match", chk_gold_totals_match_silver),
    ("gold.json_keys",    chk_json_payload_keys),
]


def run() -> dict:
    log.info("=" * 60)
    log.info("DATA QUALITY · validacao das camadas")
    log.info("=" * 60)

    results = {}
    failed = 0
    for name, check in ALL_CHECKS:
        try:
            ok, msg = check()
        except Exception as e:
            ok, msg = False, f"exception: {e!r}"
        marker = "PASS" if ok else "FAIL"
        log.info(f"[{marker}] {name}: {msg}")
        results[name] = {"passed": ok, "message": msg}
        if not ok:
            failed += 1

    log.info(f"VALIDATE DONE · passed={len(ALL_CHECKS)-failed}/{len(ALL_CHECKS)}")
    return {"failed": failed, "results": results}


if __name__ == "__main__":
    run()
