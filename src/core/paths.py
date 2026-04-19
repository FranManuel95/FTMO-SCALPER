from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXTERNAL_DIR = DATA_DIR / "external"

CONFIG_DIR = ROOT / "config"
REPORTS_DIR = ROOT / "reports"
NOTEBOOKS_DIR = ROOT / "notebooks"
LOGS_DIR = ROOT / "logs"

LEAN_DIR = ROOT / "lean"
FREQTRADE_DIR = ROOT / "freqtrade"


def ensure_dirs() -> None:
    for d in [RAW_DIR, PROCESSED_DIR, EXTERNAL_DIR, REPORTS_DIR, LOGS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
