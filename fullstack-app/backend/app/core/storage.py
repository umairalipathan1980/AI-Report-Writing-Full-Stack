from pathlib import Path
from typing import Any, Dict

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REPORT_STORE: Dict[str, Dict[str, Any]] = {}
