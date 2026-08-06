"""
Simple trade journal for Project Atlas
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

JOURNAL_PATH = Path(__file__).parent.parent / "data" / "journal.json"


class TradeJournal:
    def __init__(self):
        self.path = JOURNAL_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> List[Dict[str, Any]]:
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def _write(self, data: List[Dict[str, Any]]):
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def add_entry(self, entry: Dict[str, Any]):
        data = self._read()
        entry["timestamp"] = datetime.now().isoformat()
        data.append(entry)
        self._write(data)

    def get_all(self) -> List[Dict[str, Any]]:
        return self._read()

    def clear(self):
        self._write([])
