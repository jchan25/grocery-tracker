import sqlite3
from datetime import datetime, timedelta
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
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS stores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                whole_foods_url TEXT,
                on_list INTEGER DEFAULT 1,
                store_id INTEGER,
                added_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (store_id) REFERENCES stores (id),
                FOREIGN KEY (added_by) REFERENCES users (id)
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                user_id INTEGER,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                price REAL,
                on_sale INTEGER DEFAULT 0,
                FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id)
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

            CREATE INDEX IF NOT EXISTS idx_purchases_item
            ON purchases (item_id, purchased_at DESC);

            CREATE TABLE IF NOT EXISTS store_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                from_store_id INTEGER,
                to_store_id INTEGER,
                changed_by INTEGER,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE,
                FOREIGN KEY (from_store_id) REFERENCES stores (id),
                FOREIGN KEY (to_store_id) REFERENCES stores (id),
                FOREIGN KEY (changed_by) REFERENCES users (id)
            );
        """)

        # Add columns to existing tables if they don't exist
        try:
            conn.execute("ALTER TABLE items ADD COLUMN store_id INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE items ADD COLUMN added_by INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE items ADD COLUMN occasional INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE items ADD COLUMN target_frequency INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE purchases ADD COLUMN user_id INTEGER")
        except sqlite3.OperationalError:
            pass

        conn.commit()

def add_item(name, whole_foods_url=None, image_url=None, store_id=None, added_by=None, occasional=False):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO items (name, whole_foods_url, image_url, on_list, store_id, added_by, occasional) VALUES (?, ?, ?, 1, ?, ?, ?)",
            (name, whole_foods_url, image_url, store_id, added_by, 1 if occasional else 0)
        )
        conn.commit()
        return cursor.lastrowid

def get_all_items():
    """Get all items with purchase stats"""
    with get_db() as conn:
        items = conn.execute("""
            SELECT i.*,
                   COUNT(p.id) as purchase_count,
                   MAX(p.purchased_at) as last_purchased,
                   ph.price as current_price,
                   ph.on_sale
            FROM items i
            LEFT JOIN purchases p ON p.item_id = i.id
            LEFT JOIN price_history ph ON ph.id = (
                SELECT id FROM price_history
                WHERE item_id = i.id
                ORDER BY checked_at DESC
                LIMIT 1
            )
            GROUP BY i.id
            ORDER BY i.on_list DESC, i.created_at DESC
        """).fetchall()

        result = []
        for item in items:
            item_dict = dict(item)
            item_dict['frequency_days'] = calculate_frequency(item['id'])
            item_dict['next_purchase'] = predict_next_purchase(item['id'])
            result.append(item_dict)
        return result

def get_items_on_list():
    """Get items currently on the shopping list"""
    with get_db() as conn:
        items = conn.execute("""
            SELECT i.*,
                   COUNT(p.id) as purchase_count,
                   MAX(p.purchased_at) as last_purchased,
                   ph.price as current_price,
                   ph.on_sale,
                   s.name as store_name,
                   u.name as added_by_name
            FROM items i
            LEFT JOIN purchases p ON p.item_id = i.id
            LEFT JOIN price_history ph ON ph.id = (
                SELECT id FROM price_history
                WHERE item_id = i.id
                ORDER BY checked_at DESC
                LIMIT 1
            )
            LEFT JOIN stores s ON i.store_id = s.id
            LEFT JOIN users u ON i.added_by = u.id
            WHERE i.on_list = 1
            GROUP BY i.id
            ORDER BY i.created_at DESC
        """).fetchall()

        result = []
        for item in items:
            item_dict = dict(item)
            item_dict['frequency_days'] = calculate_frequency(item['id'])
            result.append(item_dict)
        return result

def get_frequent_items():
    """Get items not on list, ordered by purchase frequency (excludes occasional items)"""
    with get_db() as conn:
        items = conn.execute("""
            SELECT i.*,
                   COUNT(p.id) as purchase_count,
                   MAX(p.purchased_at) as last_purchased,
                   ph.price as current_price,
                   ph.on_sale,
                   s.name as store_name,
                   u.name as added_by_name
            FROM items i
            LEFT JOIN purchases p ON p.item_id = i.id
            LEFT JOIN price_history ph ON ph.id = (
                SELECT id FROM price_history
                WHERE item_id = i.id
                ORDER BY checked_at DESC
                LIMIT 1
            )
            LEFT JOIN stores s ON i.store_id = s.id
            LEFT JOIN users u ON i.added_by = u.id
            WHERE i.on_list = 0 AND (i.occasional = 0 OR i.occasional IS NULL)
            GROUP BY i.id
            HAVING purchase_count >= 1
            ORDER BY purchase_count DESC, last_purchased DESC
            LIMIT 20
        """).fetchall()

        result = []
        for item in items:
            item_dict = dict(item)
            item_dict['frequency_days'] = calculate_frequency(item['id'])
            item_dict['next_purchase'] = predict_next_purchase(item['id'])
            result.append(item_dict)
        return result

def calculate_frequency(item_id):
    """Calculate average days between purchases"""
    with get_db() as conn:
        purchases = conn.execute(
            "SELECT purchased_at FROM purchases WHERE item_id = ? ORDER BY purchased_at",
            (item_id,)
        ).fetchall()

        if len(purchases) < 2:
            return None

        # Calculate intervals between purchases
        intervals = []
        for i in range(1, len(purchases)):
            prev = datetime.fromisoformat(purchases[i-1]['purchased_at'])
            curr = datetime.fromisoformat(purchases[i]['purchased_at'])
            days = (curr - prev).days
            if days > 0:  # Ignore same-day purchases
                intervals.append(days)

        if not intervals:
            return None

        return round(sum(intervals) / len(intervals))

def predict_next_purchase(item_id):
    """Predict when item will be needed next"""
    with get_db() as conn:
        # Get item info including target_frequency
        item = conn.execute(
            "SELECT target_frequency FROM items WHERE id = ?",
            (item_id,)
        ).fetchone()

        last = conn.execute(
            "SELECT purchased_at FROM purchases WHERE item_id = ? ORDER BY purchased_at DESC LIMIT 1",
            (item_id,)
        ).fetchone()

        if not last:
            return None

        # Use target_frequency if set, otherwise calculate from purchases
        freq = item['target_frequency'] if item and item['target_frequency'] else calculate_frequency(item_id)
        if not freq:
            return None

        last_date = datetime.fromisoformat(last['purchased_at'])
        next_date = last_date + timedelta(days=freq)
        return next_date.strftime('%Y-%m-%d')

def get_item(item_id):
    with get_db() as conn:
        item = conn.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        return dict(item) if item else None

def update_item(item_id, name=None, whole_foods_url=None, image_url=None, on_list=None):
    with get_db() as conn:
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if whole_foods_url is not None:
            updates.append("whole_foods_url = ?")
            params.append(whole_foods_url)
        if image_url is not None:
            updates.append("image_url = ?")
            params.append(image_url)
        if on_list is not None:
            updates.append("on_list = ?")
            params.append(1 if on_list else 0)

        if updates:
            params.append(item_id)
            conn.execute(
                f"UPDATE items SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()

def delete_item(item_id):
    with get_db() as conn:
        conn.execute("DELETE FROM purchases WHERE item_id = ?", (item_id,))
        conn.execute("DELETE FROM price_history WHERE item_id = ?", (item_id,))
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()

def record_purchase(item_id, price=None, on_sale=False, user_id=None):
    """Record a purchase and remove item from list"""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO purchases (item_id, price, on_sale, user_id) VALUES (?, ?, ?, ?)",
            (item_id, price, 1 if on_sale else 0, user_id)
        )
        conn.execute("UPDATE items SET on_list = 0 WHERE id = ?", (item_id,))
        conn.commit()

def add_to_list(item_id):
    """Add an item back to the shopping list"""
    with get_db() as conn:
        conn.execute("UPDATE items SET on_list = 1 WHERE id = ?", (item_id,))
        conn.commit()

def get_purchase_history(item_id, limit=30):
    with get_db() as conn:
        history = conn.execute(
            """SELECT * FROM purchases
               WHERE item_id = ?
               ORDER BY purchased_at DESC
               LIMIT ?""",
            (item_id, limit)
        ).fetchall()
        return [dict(h) for h in history]

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
            WHERE ph.on_sale = 1 AND i.on_list = 1
        """).fetchall()
        return [dict(item) for item in items]

# User management
def add_user(name):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (name) VALUES (?)",
            (name,)
        )
        conn.commit()
        return cursor.lastrowid

def get_all_users():
    with get_db() as conn:
        users = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
        return [dict(u) for u in users]

def delete_user(user_id):
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

# Store management
def add_store(name):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO stores (name) VALUES (?)",
            (name,)
        )
        conn.commit()
        return cursor.lastrowid

def get_all_stores():
    with get_db() as conn:
        stores = conn.execute("SELECT * FROM stores ORDER BY name").fetchall()
        return [dict(s) for s in stores]

def delete_store(store_id):
    with get_db() as conn:
        conn.execute("DELETE FROM stores WHERE id = ?", (store_id,))
        conn.commit()

def change_item_store(item_id, new_store_id, changed_by=None):
    """Change item's store and log the change"""
    with get_db() as conn:
        # Get current store
        current = conn.execute("SELECT store_id FROM items WHERE id = ?", (item_id,)).fetchone()
        from_store_id = current['store_id'] if current else None

        # Log the change
        conn.execute(
            "INSERT INTO store_history (item_id, from_store_id, to_store_id, changed_by) VALUES (?, ?, ?, ?)",
            (item_id, from_store_id, new_store_id, changed_by)
        )

        # Update the item
        conn.execute("UPDATE items SET store_id = ? WHERE id = ?", (new_store_id, item_id))
        conn.commit()

def get_store_history(item_id):
    """Get store change history for an item"""
    with get_db() as conn:
        history = conn.execute("""
            SELECT sh.*,
                   fs.name as from_store_name,
                   ts.name as to_store_name,
                   u.name as changed_by_name
            FROM store_history sh
            LEFT JOIN stores fs ON sh.from_store_id = fs.id
            LEFT JOIN stores ts ON sh.to_store_id = ts.id
            LEFT JOIN users u ON sh.changed_by = u.id
            WHERE sh.item_id = ?
            ORDER BY sh.changed_at DESC
        """, (item_id,)).fetchall()
        return [dict(h) for h in history]

def set_target_frequency(item_id, days):
    """Set target frequency for an item (in days)"""
    with get_db() as conn:
        conn.execute("UPDATE items SET target_frequency = ? WHERE id = ?", (days, item_id))
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
