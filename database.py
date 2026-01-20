import sqlite3
from datetime import datetime
from contextlib import contextmanager

DATABASE_PATH = "grocery.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                whole_foods_url TEXT,
                purchased INTEGER DEFAULT 0,
                purchase_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                price REAL,
                regular_price REAL,
                on_sale INTEGER DEFAULT 0,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_price_history_item
            ON price_history (item_id, checked_at DESC);
        """)
        conn.commit()

def add_item(name, whole_foods_url=None):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO items (name, whole_foods_url) VALUES (?, ?)",
            (name, whole_foods_url)
        )
        conn.commit()
        return cursor.lastrowid

def get_all_items():
    with get_db() as conn:
        items = conn.execute("""
            SELECT i.*,
                   ph.price as current_price,
                   ph.regular_price,
                   ph.on_sale,
                   ph.checked_at as last_checked
            FROM items i
            LEFT JOIN price_history ph ON ph.id = (
                SELECT id FROM price_history
                WHERE item_id = i.id
                ORDER BY checked_at DESC
                LIMIT 1
            )
            ORDER BY i.created_at DESC
        """).fetchall()
        return [dict(item) for item in items]

def get_item(item_id):
    with get_db() as conn:
        item = conn.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        return dict(item) if item else None

def update_item(item_id, name=None, whole_foods_url=None, purchased=None):
    with get_db() as conn:
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if whole_foods_url is not None:
            updates.append("whole_foods_url = ?")
            params.append(whole_foods_url)
        if purchased is not None:
            updates.append("purchased = ?")
            params.append(1 if purchased else 0)
            if purchased:
                conn.execute(
                    "UPDATE items SET purchase_count = purchase_count + 1 WHERE id = ?",
                    (item_id,)
                )

        if updates:
            params.append(item_id)
            conn.execute(
                f"UPDATE items SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()

def delete_item(item_id):
    with get_db() as conn:
        conn.execute("DELETE FROM price_history WHERE item_id = ?", (item_id,))
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()

def add_price_record(item_id, price, regular_price=None, on_sale=False):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO price_history (item_id, price, regular_price, on_sale)
               VALUES (?, ?, ?, ?)""",
            (item_id, price, regular_price, 1 if on_sale else 0)
        )
        conn.commit()

def get_price_history(item_id, limit=30):
    with get_db() as conn:
        history = conn.execute(
            """SELECT * FROM price_history
               WHERE item_id = ?
               ORDER BY checked_at DESC
               LIMIT ?""",
            (item_id, limit)
        ).fetchall()
        return [dict(h) for h in history]

def get_items_with_urls():
    """Get all items that have Whole Foods URLs for price checking"""
    with get_db() as conn:
        items = conn.execute(
            "SELECT * FROM items WHERE whole_foods_url IS NOT NULL AND whole_foods_url != ''"
        ).fetchall()
        return [dict(item) for item in items]

def get_sale_items():
    """Get all items currently on sale"""
    with get_db() as conn:
        items = conn.execute("""
            SELECT i.*, ph.price, ph.regular_price, ph.on_sale
            FROM items i
            JOIN price_history ph ON ph.id = (
                SELECT id FROM price_history
                WHERE item_id = i.id
                ORDER BY checked_at DESC
                LIMIT 1
            )
            WHERE ph.on_sale = 1
        """).fetchall()
        return [dict(item) for item in items]

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
