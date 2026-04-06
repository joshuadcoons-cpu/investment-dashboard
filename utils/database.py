import sqlite3
import json
import copy
from pathlib import Path
from datetime import date, datetime

DB_PATH   = Path(__file__).parent.parent / "finance.db"
JSON_PATH = Path(__file__).parent.parent / "assumptions.json"


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
    con.execute("""
        CREATE TABLE IF NOT EXISTS net_worth_history (
            date        TEXT PRIMARY KEY,
            net_worth   REAL,
            total_assets REAL,
            total_liabilities REAL,
            investments REAL,
            home_equity REAL,
            cash        REAL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            date    TEXT NOT NULL,
            account TEXT,
            ticker  TEXT,
            action  TEXT,
            shares  REAL,
            price   REAL,
            notes   TEXT
        )
    """)
    con.commit()
    con.close()


# ── Assumptions ─────────────────────────────────────────────────────────────

def _get_version(data: dict) -> int:
    """Extract _data_version integer from an assumptions dict (0 if missing)."""
    return int(data.get("_data_version", 0))


def load_assumptions():
    """Return saved assumptions dict or None if no saved data exists.

    Reads BOTH assumptions.json and the SQLite DB, then returns whichever
    has the higher _data_version.  When we push a new assumptions.json to git
    with an incremented version, it always wins over the cloud's stale DB.
    """
    json_data = None
    db_data   = None

    if JSON_PATH.exists():
        try:
            json_data = json.loads(JSON_PATH.read_text(encoding="utf-8"),
                                   object_hook=_date_decoder)
        except Exception:
            pass

    _init()
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT value FROM settings WHERE key = 'assumptions'"
    ).fetchone()
    con.close()
    if row:
        try:
            db_data = json.loads(row[0], object_hook=_date_decoder)
        except Exception:
            pass

    # Pick the higher-versioned source
    if json_data is not None and db_data is not None:
        return json_data if _get_version(json_data) >= _get_version(db_data) else db_data
    return json_data or db_data or None


def save_assumptions(assumptions: dict) -> None:
    """Persist the assumptions dict to SQLite only.

    assumptions.json is READ-ONLY (git-tracked).  We never write to it at
    runtime so that Streamlit Cloud's git deploy can always overwrite it
    cleanly with our latest pushed version.
    """
    data = copy.deepcopy(assumptions)
    _init()
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('assumptions', ?)",
        (json.dumps(data, cls=_DateEncoder),),
    )
    con.commit()
    con.close()


# ── Net Worth History ───────────────────────────────────────────────────────

def log_net_worth(as_of: date, net_worth: float, total_assets: float,
                  total_liabilities: float, investments: float,
                  home_equity: float, cash: float) -> None:
    _init()
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """INSERT OR REPLACE INTO net_worth_history
           (date, net_worth, total_assets, total_liabilities,
            investments, home_equity, cash)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (as_of.isoformat(), net_worth, total_assets, total_liabilities,
         investments, home_equity, cash),
    )
    con.commit()
    con.close()


def get_net_worth_history() -> list[dict]:
    _init()
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT date, net_worth, total_assets, total_liabilities, "
        "investments, home_equity, cash "
        "FROM net_worth_history ORDER BY date"
    ).fetchall()
    con.close()
    return [
        {"date": r[0], "net_worth": r[1], "total_assets": r[2],
         "total_liabilities": r[3], "investments": r[4],
         "home_equity": r[5], "cash": r[6]}
        for r in rows
    ]


# ── Transactions ────────────────────────────────────────────────────────────

def add_transaction(txn_date: date, account: str, ticker: str,
                    action: str, shares: float, price: float,
                    notes: str = "") -> None:
    _init()
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """INSERT INTO transactions
           (date, account, ticker, action, shares, price, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (txn_date.isoformat(), account, ticker, action, shares, price, notes),
    )
    con.commit()
    con.close()


def get_transactions() -> list[dict]:
    _init()
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT id, date, account, ticker, action, shares, price, notes "
        "FROM transactions ORDER BY date DESC"
    ).fetchall()
    con.close()
    return [
        {"id": r[0], "date": r[1], "account": r[2], "ticker": r[3],
         "action": r[4], "shares": r[5], "price": r[6], "notes": r[7]}
        for r in rows
    ]


def delete_transaction(txn_id: int) -> None:
    _init()
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
    con.commit()
    con.close()
