import sqlite3
import json
import copy
from pathlib import Path
from datetime import date

DB_PATH = Path(__file__).parent.parent / "finance.db"


class _DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return {"__date__": obj.isoformat()}
        return super().default(obj)


def _date_decoder(obj):
    if "__date__" in obj:
        return date.fromisoformat(obj["__date__"])
    return obj


def _init():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    con.commit()
    con.close()


def load_assumptions():
    """Return saved assumptions dict or None if no saved data exists."""
    _init()
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT value FROM settings WHERE key = 'assumptions'"
    ).fetchone()
    con.close()
    if row:
        return json.loads(row[0], object_hook=_date_decoder)
    return None


def save_assumptions(assumptions: dict) -> None:
    """Persist the assumptions dict to SQLite."""
    _init()
    data = copy.deepcopy(assumptions)
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('assumptions', ?)",
        (json.dumps(data, cls=_DateEncoder),),
    )
    con.commit()
    con.close()
