"""ATLAS CAPITAL — Improvement Suggestion Tracker.

Stores suggestions/ideas from:
  - portal Member Comments (approved)
  - email replies to Hermes (from Dr. King or Penn)
in data/improvements.json (gitignored). Each entry:
  {id, source, text, status, date, note}
status: new -> accepted | rejected | done
"""
from __future__ import annotations
import os, json, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "improvements.json")


def _load():
    try:
        return json.load(open(PATH))
    except Exception:
        return []


def _save(items):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    json.dump(items, open(PATH, "w"), indent=2)


def add(source: str, text: str, note: str = "") -> dict:
    items = _load()
    item = {
        "id": f"IMP-{len(items)+1:03d}",
        "source": source,
        "text": text.strip(),
        "status": "new",
        "date": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "note": note,
    }
    items.append(item)
    _save(items)
    return item


def set_status(iid: str, status: str, note: str = "") -> bool:
    items = _load()
    for it in items:
        if it["id"] == iid:
            it["status"] = status
            if note:
                it["note"] = note
            _save(items)
            return True
    return False


def all_items():
    return _load()


def new_items():
    return [i for i in _load() if i["status"] == "new"]


def looks_like_suggestion(text: str) -> bool:
    t = text.lower()
    keys = ["suggest", "improve", "idea", "what if", "we could", "we should",
            "should we", "better if", "how about", "recommend", "consider",
            "proposal", "maybe try", "why not", "add a", "add an"]
    return any(k in t for k in keys)


if __name__ == "__main__":
    for i in all_items():
        print(f"{i['id']} [{i['status']}] {i['source']}: {i['text'][:70]}")
