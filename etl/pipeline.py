"""
Orquestrador do pipeline ETL BanVic.

Roda na ordem:
    bronze  ->  silver  ->  gold  ->  validate

Cada etapa loga inicio/fim e duracao. Falhas em qualquer etapa abortam
o pipeline com codigo de saida != 0 (util pra CI/cron).

Uso:
    python -m etl.pipeline                  # roda tudo
    python -m etl.pipeline --skip-bronze    # pula a re-ingestao
    python -m etl.pipeline --only validate  # so as checagens
"""
import argparse
import sys
import time
from datetime import datetime

from etl import bronze, silver, gold, validate
from etl.logger import get_logger

log = get_logger("pipeline")

STAGES = {
    "bronze":   bronze.run,
    "silver":   silver.run,
    "gold":     gold.run,
    "validate": validate.run,
}


def _run_stage(name, fn):
    log.info(f">>> START {name}")
    t0 = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t0
    log.info(f"<<< END   {name}  ({dt:.2f}s)")
    return out


def main():
    parser = argparse.ArgumentParser(description="BanVic ETL pipeline")
    parser.add_argument("--skip-bronze", action="store_true",
                        help="pula a re-ingestao dos CSVs (usa bronze ja gerado)")
    parser.add_argument("--only", choices=list(STAGES.keys()),
                        help="roda somente uma etapa")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info(f"BANVIC ETL · inicio {datetime.now().isoformat(timespec='seconds')}")
    log.info("=" * 60)

    if args.only:
        _run_stage(args.only, STAGES[args.only])
        return 0

    sequence = ["bronze", "silver", "gold", "validate"]
    if args.skip_bronze:
        sequence.remove("bronze")
        log.info("opcao --skip-bronze: pulando ingestao raw")

    summary = {}
    t0 = time.perf_counter()
    for stage in sequence:
        try:
            summary[stage] = _run_stage(stage, STAGES[stage])
        except Exception as e:
            log.error(f"FALHA em {stage}: {e!r}")
            return 1
    dt = time.perf_counter() - t0

    log.info("=" * 60)
    log.info(f"BANVIC ETL · sucesso em {dt:.2f}s")
    log.info("=" * 60)

    # Checa se a validacao acusou falhas
    if isinstance(summary.get("validate"), dict) and summary["validate"].get("failed", 0) > 0:
        log.warning(f"validacao detectou {summary['validate']['failed']} check(s) com falha "
                    f"(pipeline concluiu, mas revise os logs)")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
