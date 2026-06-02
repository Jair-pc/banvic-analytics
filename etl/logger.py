"""
Logger compartilhado por todas as camadas do ETL.
- Escreve em logs/etl_YYYYMMDD.log
- Tambem ecoa no stdout
- Cada chamada a get_logger(name) reusa o mesmo handler (sem duplicacao)
"""
import logging
from datetime import datetime
from etl.config import LOGS_DIR


def get_logger(name: str = "banvic_etl") -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_file = LOGS_DIR / f"etl_{datetime.now().strftime('%Y%m%d')}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger
