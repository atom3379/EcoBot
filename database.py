import sqlite3
import time

DB_PATH = "finance.db"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now():
    return int(time.time())


def init_db():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_id INTEGER,
                started_at INTEGER NOT NULL,
                ended_at INTEGER,
                FOREIGN KEY(set_id) REFERENCES sets(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_id INTEGER NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                amount INTEGER NOT NULL CHECK(amount > 0),
                description TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY(day_id) REFERENCES days(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                processed_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS set_views (
                set_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY(set_id) REFERENCES sets(id)
            )
        """)

        # Migrate the old date-based days table without renaming it.
        # Renaming it breaks existing foreign keys from transactions.
        columns = [r[1] for r in conn.execute("PRAGMA table_info(days)").fetchall()]
        if "date" in columns:
            import datetime
            if "set_id" not in columns:
                conn.execute("ALTER TABLE days ADD COLUMN set_id INTEGER")
            if "started_at" not in columns:
                conn.execute("ALTER TABLE days ADD COLUMN started_at INTEGER")
            if "ended_at" not in columns:
                conn.execute("ALTER TABLE days ADD COLUMN ended_at INTEGER")
            rows = conn.execute("SELECT id, date, started_at, ended_at FROM days").fetchall()
            for row in rows:
                started_ts = row[2]
                if not started_ts:
                    try:
                        started_ts = int(datetime.datetime.fromisoformat(row[1]).timestamp())
                    except Exception:
                        started_ts = now()
                ended_ts = row[3]
                if ended_ts and isinstance(ended_ts, str):
                    try:
                        ended_ts = int(datetime.datetime.fromisoformat(ended_ts).timestamp())
                    except Exception:
                        ended_ts = now()
                conn.execute(
                    "UPDATE days SET started_at = ?, ended_at = ? WHERE id = ?",
                    (started_ts, ended_ts, row[0]),
                )


def create_set(name):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO sets (name, created_at) VALUES (?, ?)", (name, now())
        )
        return cur.lastrowid


def get_set(ref):
    with connect() as conn:
        if str(ref).isdigit():
            return conn.execute("SELECT * FROM sets WHERE id = ?", (int(ref),)).fetchone()
        return conn.execute("SELECT * FROM sets WHERE name = ? COLLATE NOCASE", (str(ref),)).fetchone()


def rename_set(ref, name):
    item = get_set(ref)
    if not item:
        return False
    with connect() as conn:
        conn.execute("UPDATE sets SET name = ? WHERE id = ?", (name, item["id"]))
    return True


def get_or_create_active_day(set_id=None):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM days WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            if set_id is not None and row["set_id"] != set_id:
                conn.execute("UPDATE days SET set_id = ? WHERE id = ?", (set_id, row["id"]))
                row = conn.execute("SELECT * FROM days WHERE id = ?", (row["id"],)).fetchone()
            return row
        cur = conn.execute(
            "INSERT INTO days (set_id, started_at) VALUES (?, ?)", (set_id, now())
        )
        return conn.execute("SELECT * FROM days WHERE id = ?", (cur.lastrowid,)).fetchone()


def reset_day(set_id=None):
    with connect() as conn:
        active = conn.execute(
            "SELECT * FROM days WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if active:
            conn.execute("UPDATE days SET ended_at = ? WHERE id = ?", (now(), active["id"]))
            if set_id is None:
                set_id = active["set_id"]
        cur = conn.execute(
            "INSERT INTO days (set_id, started_at) VALUES (?, ?)", (set_id, now())
        )
        return conn.execute("SELECT * FROM days WHERE id = ?", (cur.lastrowid,)).fetchone()


def delete_day(day_id):
    with connect() as conn:
        day = conn.execute("SELECT * FROM days WHERE id = ?", (day_id,)).fetchone()
        if not day:
            return False
        if day["ended_at"] is None:
            return False
        conn.execute("DELETE FROM transactions WHERE day_id = ?", (day_id,))
        conn.execute("DELETE FROM days WHERE id = ?", (day_id,))
        return True


def get_active_day():
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM days WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()


def add_transaction(tx_type, amount, description, message_id=None):
    with connect() as conn:
        day = conn.execute(
            "SELECT * FROM days WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not day:
            raise ValueError("NO_ACTIVE_SESSION")
        if message_id is not None:
            exists = conn.execute(
                "SELECT 1 FROM processed_messages WHERE message_id = ?", (str(message_id),)
            ).fetchone()
            if exists:
                raise ValueError("DUPLICATE_MESSAGE")
            conn.execute(
                "INSERT INTO processed_messages (message_id, processed_at) VALUES (?, ?)",
                (str(message_id), now()),
            )
        conn.execute(
            "INSERT INTO transactions (day_id, type, amount, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (day["id"], tx_type, amount, description, now()),
        )


def get_day_transactions(day_id):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM transactions WHERE day_id = ? ORDER BY id", (day_id,)
        ).fetchall()


def get_day_summary(day_id):
    rows = get_day_transactions(day_id)
    income = sum(r["amount"] for r in rows if r["type"] == "income")
    expense = sum(r["amount"] for r in rows if r["type"] == "expense")
    return rows, income, expense, income - expense


def get_set_days(set_id):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM days WHERE set_id = ? ORDER BY started_at", (set_id,)
        ).fetchall()


def get_set_summary(set_id):
    days = get_set_days(set_id)
    rows = []
    for day in days:
        rows.extend(get_day_transactions(day["id"]))
    income = sum(r["amount"] for r in rows if r["type"] == "income")
    expense = sum(r["amount"] for r in rows if r["type"] == "expense")
    return days, rows, income, expense, income - expense


def save_set_view(set_id, guild_id, channel_id, user_id, expires_at):
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO set_views (set_id, guild_id, channel_id, user_id, expires_at) VALUES (?, ?, ?, ?, ?)",
            (set_id, guild_id, channel_id, user_id, expires_at),
        )


def get_set_view(set_id):
    with connect() as conn:
        return conn.execute("SELECT * FROM set_views WHERE set_id = ?", (set_id,)).fetchone()


def delete_set_view(set_id):
    with connect() as conn:
        conn.execute("DELETE FROM set_views WHERE set_id = ?", (set_id,))


def get_expired_views(timestamp=None):
    timestamp = now() if timestamp is None else timestamp
    with connect() as conn:
        return conn.execute("SELECT * FROM set_views WHERE expires_at <= ?", (timestamp,)).fetchall()


def get_all_set_views():
    with connect() as conn:
        return conn.execute("SELECT * FROM set_views").fetchall()


def clear_all():
    with connect() as conn:
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM days")
        conn.execute("DELETE FROM set_views")
        conn.execute("DELETE FROM sets")
        conn.execute("DELETE FROM processed_messages")
