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

def load_assumptions():
    """Return saved assumptions dict or None if no saved data exists.

    Prefers assumptions.json over the SQLite DB so that git-pushed updates
    take effect on Streamlit Cloud (which persists runtime DB changes across
    redeploys but properly overwrites tracked text files on each deploy).
    """
    # Try JSON first — it wins if it exists
    if JSON_PATH.exists():
        try:
            return json.loads(JSON_PATH.read_text(encoding="utf-8"),
                              object_hook=_date_decoder)
        except Exception:
            pass
    # Fall back to SQLite
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
    """Persist the assumptions dict to both JSON and SQLite."""
    data = copy.deepcopy(assumptions)
    encoded = json.dumps(data, cls=_DateEncoder, indent=2)
    # JSON (primary — git-trackable, survives Streamlit Cloud redeploys)
    JSON_PATH.write_text(encoded, encoding="utf-8")
    # SQLite (backup / local use)
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
