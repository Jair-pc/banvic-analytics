"""
Configuracao central do pipeline ETL BanVic.
Define paths, encodings, e mapeamentos usados pelas camadas Bronze/Silver/Gold.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (relativos a raiz do repo)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent

RAW_DIR    = ROOT / "data" / "raw"
BRONZE_DIR = ROOT / "data" / "bronze"
SILVER_DIR = ROOT / "data" / "silver"
GOLD_DIR   = ROOT / "data" / "gold"

OUTPUT_DIR = ROOT / "output"
LOGS_DIR   = ROOT / "logs"

OUTPUT_JSON = OUTPUT_DIR / "banvic_v2_report.json"

# ---------------------------------------------------------------------------
# Mapeamento de tabelas raw -> nome canonico no pipeline
# ---------------------------------------------------------------------------
RAW_TABLES = {
    "agencias":            "agencias.csv",
    "clientes":            "clientes.csv",
    "colaboradores":       "colaboradores.csv",
    "colaborador_agencia": "colaborador_agencia.csv",
    "contas":              "contas.csv",
    "propostas_credito":   "propostas_credito.csv",
    "transacoes":          "transacoes.csv",
    "ipca":                "ipca.csv",
}

# ---------------------------------------------------------------------------
# Encoding fallback para os CSVs do desafio (alguns tem BOM, outros sao latin-1)
# ---------------------------------------------------------------------------
ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")

# ---------------------------------------------------------------------------
# Data de referencia para calculo de idade/faixa etaria
# ---------------------------------------------------------------------------
REFERENCE_DATE = "2024-01-01"

# ---------------------------------------------------------------------------
# Mapeamentos de dominio
# ---------------------------------------------------------------------------
MES_PT = {
    "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4,  "MAI": 5,  "JUN": 6,
    "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12,
}

FAIXAS_ETARIAS = ["Jovem (<25)", "Adulto (25-59)", "Idoso (60+)"]
ESTADOS_ATIVOS  = ["SP", "RJ", "RS", "SC", "PE"]
