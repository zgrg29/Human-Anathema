"""Load immutable game definitions from JSON files."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_catalog():
    catalog = {}
    for path in sorted(DATA_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as file:
            catalog[path.stem] = json.load(file)
    return catalog
